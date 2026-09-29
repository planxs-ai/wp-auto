"""쿠팡 파트너스 Open API 클라이언트 — HMAC 서명·예산·브레이커·원본 보존.

서명 규격은 파트너스 공식 예제 기준 [훈련 지식·2차 출처]:
  Authorization: CEA algorithm=HmacSHA256, access-key=<KEY>, signed-date=<yyMMdd'T'HHmmss'Z'>, signature=<hex>
  message = signed_date + METHOD + path + query   (query는 '?' 없이)
대표 계정 문서와 대조 후 다르면 sign()만 고친다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from .core import Budget, CircuitBreaker, Store, api_call_row, now_kst

log = logging.getLogger("deals.coupang")


def signed_date(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%y%m%dT%H%M%SZ")


def sign(secret: str, access_key: str, method: str, path: str, query: str = "", dt: datetime | None = None) -> str:
    sd = signed_date(dt)
    message = sd + method.upper() + path + query
    sig = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"CEA algorithm=HmacSHA256, access-key={access_key}, signed-date={sd}, signature={sig}"


class CoupangClient:
    def __init__(self, cfg: dict, store: Store | None, budget: Budget, breaker: CircuitBreaker,
                 access_key: str | None = None, secret_key: str | None = None,
                 session: requests.Session | None = None, dry: bool = False):
        self.cfg = cfg
        self.api = cfg["api"]
        self.fm = cfg["field_map"]
        self.store = store
        self.budget = budget
        self.breaker = breaker
        self.ak = access_key or os.environ.get("COUPANG_ACCESS_KEY", "")
        self.sk = secret_key or os.environ.get("COUPANG_SECRET_KEY", "")
        self.sub_id = os.environ.get("COUPANG_SUB_ID", "")
        self.s = session or requests.Session()
        self.dry = dry
        self.calls = 0
        self.errors = 0

    # ── 저수준 ──
    def _request(self, op: str, method: str, path: str, params: dict | None = None, body: Any = None) -> Any:
        if not self.ak or not self.sk:
            raise RuntimeError("COUPANG_ACCESS_KEY / COUPANG_SECRET_KEY 환경변수가 없다")
        self.budget.take(op)
        query = urlencode({k: v for k, v in (params or {}).items() if v not in (None, "")})
        url = f"{self.api['base_url']}{path}" + (f"?{query}" if query else "")
        last_err = "unknown"
        for attempt in range(self.api.get("retries", 2) + 1):
            t0 = time.monotonic()
            status = "ERR"
            try:
                headers = {"Authorization": sign(self.sk, self.ak, method, path, query),
                           "Content-Type": "application/json;charset=UTF-8"}
                r = self.s.request(method, url, headers=headers,
                                   data=json.dumps(body) if body is not None else None,
                                   timeout=self.api.get("timeout_sec", 20))
                ms = int((time.monotonic() - t0) * 1000)
                if r.status_code >= 500:
                    last_err = f"{r.status_code}"
                    self._log_call(op, f"HTTP{r.status_code}", ms, params)
                    self.breaker.fail(last_err)
                    time.sleep(1.5 * (attempt + 1))
                    continue
                try:
                    data = r.json()
                except ValueError:
                    last_err = "non-json"
                    self._log_call(op, "NONJSON", ms, params)
                    self.breaker.fail(last_err)
                    continue
                if r.status_code >= 400:
                    # 4xx는 우리 잘못(서명·권한·한도) — 브레이커 대상 아님, 즉시 반환 실패
                    self._log_call(op, f"HTTP{r.status_code}", ms, params)
                    self.errors += 1
                    raise RuntimeError(f"{op} HTTP {r.status_code}: {str(data)[:300]}")
                code = str(data.get(self.fm["envelope_code"], "0"))
                if code != str(self.fm["envelope_ok_code"]):
                    self._log_call(op, f"RCODE{code}", ms, params)
                    self.errors += 1
                    raise RuntimeError(f"{op} rCode={code}: {str(data)[:300]}")
                status = "OK"
                self._log_call(op, status, ms, params)
                self.breaker.ok()
                self.calls += 1
                self._save_raw(op, params, data)
                return data.get(self.fm["envelope_data"])
            except (requests.ConnectionError, requests.Timeout) as e:
                ms = int((time.monotonic() - t0) * 1000)
                last_err = type(e).__name__
                self._log_call(op, last_err, ms, params)
                self.breaker.fail(last_err)
                time.sleep(1.5 * (attempt + 1))
        self.errors += 1
        raise RuntimeError(f"{op} failed after retries: {last_err}")

    def _log_call(self, op, status, ms, params):
        if self.store is not None:
            try:
                self.store.upsert("deal_api_calls", [api_call_row(op, status, ms, params)], "id")
            except Exception as e:  # 로그 실패가 수집을 막으면 안 된다
                log.warning("api_call log failed: %s", e)

    def _save_raw(self, op, params, payload):
        if self.store is not None:
            try:
                self.store.upsert("deal_raw_payloads",
                                  [{"op": op, "params": params or {}, "fetched_at": now_kst().isoformat(), "payload": payload}],
                                  "id")
            except Exception as e:
                log.warning("raw save failed: %s", e)

    # ── 오퍼레이션 ──
    def goldbox(self) -> list[dict]:
        return self._request("goldbox", "GET", self.api["paths"]["goldbox"], {"subId": self.sub_id}) or []

    def bestcategory(self, category_id: str, limit: int = 100) -> list[dict]:
        path = self.api["paths"]["bestcategory"].format(category_id=category_id)
        return self._request("bestcategory", "GET", path, {"limit": limit, "subId": self.sub_id}) or []

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        data = self._request("search", "GET", self.api["paths"]["search"],
                             {"keyword": keyword, "limit": limit, "subId": self.sub_id}) or {}
        if isinstance(data, dict):
            return data.get(self.fm["search_items"], []) or []
        return data

    def deeplinks(self, urls: list[str]) -> dict[str, str]:
        if not urls:
            return {}
        data = self._request("deeplink", "POST", self.api["paths"]["deeplink"], None,
                             {"coupangUrls": urls, **({"subId": self.sub_id} if self.sub_id else {})}) or []
        fm = self.fm["deeplink"]
        return {d.get(fm["original"]): d.get(fm["short"]) or d.get(fm["landing"]) for d in data}

    # ── 매핑 ──
    def map_product(self, raw: dict, source: str, category_hint: str = "") -> dict:
        pm = self.fm["product"]
        pid = raw.get(pm["product_id"])
        price = raw.get(pm["price"])
        return {
            "product_id": str(pid) if pid is not None else None,
            "name": raw.get(pm["name"]),
            "price": int(price) if price not in (None, "") else None,
            "image": raw.get(pm["image"]),
            "url": raw.get(pm["url"]),
            "category": raw.get(pm["category"]) or category_hint,
            "rocket": bool(raw.get(pm["rocket"])) if raw.get(pm["rocket"]) is not None else None,
            "free_shipping": raw.get(pm["free_shipping"]),
            "rank": raw.get(pm["rank"]),
            "discount_rate": raw.get(pm["discount_rate"]),
            "source": source,
            "raw": raw,
        }
