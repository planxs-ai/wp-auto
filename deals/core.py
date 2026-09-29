"""설정·시간·예산·브레이커·저장소(PostgREST/메모리)."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

log = logging.getLogger("deals")
KST = timezone(timedelta(hours=9))
HERE = Path(__file__).resolve().parent


def now_kst() -> datetime:
    return datetime.now(KST)


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else HERE / "config.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


class BudgetExceeded(RuntimeError):
    pass


class UpstreamDown(RuntimeError):
    pass


class TimeBudgetExceeded(RuntimeError):
    pass


@dataclass
class Budget:
    """호출 예산 — 일 합계 + 오퍼레이션별 시간당. 프로세스 밖(DB) 실사용을 preflight로 차감한다."""
    daily_limit: int
    hourly_limits: dict[str, int]
    used_today: int = 0
    used_hour: dict[str, int] = field(default_factory=dict)

    def preflight(self, used_today: int, used_hour: dict[str, int]) -> None:
        self.used_today = int(used_today)
        self.used_hour = {k: int(v) for k, v in used_hour.items()}

    def remaining_today(self) -> int:
        return max(0, self.daily_limit - self.used_today)

    def remaining_hour(self, op: str) -> int:
        lim = self.hourly_limits.get(op)
        if lim is None:
            return 10**9
        return max(0, lim - self.used_hour.get(op, 0))

    def take(self, op: str) -> None:
        if self.remaining_today() <= 0:
            raise BudgetExceeded(f"daily budget {self.daily_limit} exhausted")
        if self.remaining_hour(op) <= 0:
            raise BudgetExceeded(f"hourly budget for {op} ({self.hourly_limits.get(op)}) exhausted")
        self.used_today += 1
        self.used_hour[op] = self.used_hour.get(op, 0) + 1


@dataclass
class CircuitBreaker:
    threshold: int = 3
    consecutive: int = 0

    def ok(self) -> None:
        self.consecutive = 0

    def fail(self, reason: str) -> None:
        self.consecutive += 1
        if self.consecutive >= self.threshold:
            raise UpstreamDown(f"{self.consecutive} consecutive failures: {reason}")


class TimeBudget:
    def __init__(self, soft_minutes: float, hard_minutes: float):
        self.t0 = time.monotonic()
        self.soft = soft_minutes * 60
        self.hard = hard_minutes * 60

    def elapsed(self) -> float:
        return time.monotonic() - self.t0

    def soft_hit(self) -> bool:
        return self.elapsed() >= self.soft

    def check_hard(self) -> None:
        if self.elapsed() >= self.hard:
            raise TimeBudgetExceeded(f"hard time budget {self.hard/60:.0f}m hit")


# ── 저장소 ────────────────────────────────────────────────────────────
class Store:
    """PostgREST(Supabase) 저장소. 모든 쓰기는 자연키 UPSERT — 재실행해도 결과 동일."""

    def __init__(self, url: str, key: str, session: requests.Session | None = None):
        self.url = url.rstrip("/")
        self.key = key
        self.s = session or requests.Session()
        self.h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    @classmethod
    def from_env(cls) -> "Store":
        url, key = os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_KEY 환경변수가 없다")
        return cls(url, key)

    def upsert(self, table: str, rows: list[dict], on_conflict: str, ignore: bool = False) -> int:
        if not rows:
            return 0
        res = "ignore-duplicates" if ignore else "merge-duplicates"
        h = dict(self.h, Prefer=f"resolution={res},return=minimal")
        r = self.s.post(f"{self.url}/rest/v1/{table}?on_conflict={on_conflict}", headers=h,
                        data=json.dumps(rows, ensure_ascii=False, default=str), timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"upsert {table} {r.status_code}: {r.text[:300]}")
        return len(rows)

    def select(self, table: str, query: str) -> list[dict]:
        r = self.s.get(f"{self.url}/rest/v1/{table}?{query}", headers=self.h, timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"select {table} {r.status_code}: {r.text[:300]}")
        return r.json()

    def patch(self, table: str, query: str, data: dict) -> None:
        h = dict(self.h, Prefer="return=minimal")
        r = self.s.patch(f"{self.url}/rest/v1/{table}?{query}", headers=h,
                         data=json.dumps(data, ensure_ascii=False, default=str), timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"patch {table} {r.status_code}: {r.text[:300]}")

    # 편의 조회
    def calls_since(self, since_iso: str, op: str | None = None) -> int:
        q = f"select=id&ts=gte.{since_iso}" + (f"&op=eq.{op}" if op else "")
        return len(self.select("deal_api_calls", q))

    def price_history(self, product_id: str, days: int) -> list[dict]:
        since = (now_kst() - timedelta(days=days)).isoformat()
        return self.select("deal_price_snapshots",
                           f"select=ts,price,discount_rate&product_id=eq.{product_id}&ts=gte.{since}&order=ts.asc")

    def recent_events(self, product_id: str, kind: str, days: int) -> list[dict]:
        since = (now_kst() - timedelta(days=days)).isoformat()
        return self.select("deal_events",
                           f"select=id,ts,channel,msg_id&product_id=eq.{product_id}&kind=eq.{kind}&ts=gte.{since}")

    def published_today(self, channel: str) -> int:
        day = now_kst().date().isoformat()
        return len(self.select("deal_events", f"select=id&channel=eq.{channel}&ts_day=eq.{day}&msg_id=not.is.null"))


class MemoryStore(Store):
    """테스트·selftest용 인메모리 저장소 — UNIQUE 의미론을 그대로 흉내 낸다(API·DB 0콜)."""

    UNIQUE = {
        "deal_products": ("product_id",),
        "deal_price_snapshots": ("product_id", "ts_hour"),
        "deal_events": ("product_id", "kind", "ts_day", "channel"),
        "deal_runs": ("run_id",),
        "deal_api_calls": ("id",),
        "deal_raw_payloads": ("id",),
    }

    def __init__(self):  # noqa: D107 — 부모 초기화 생략(네트워크 없음)
        self.tables: dict[str, dict[tuple, dict]] = {}
        self._auto = 0

    def _key(self, table: str, row: dict) -> tuple:
        cols = self.UNIQUE.get(table, ())
        if cols == ("id",) and "id" not in row:
            self._auto += 1
            row["id"] = self._auto
        return tuple(row.get(c) for c in cols)

    def upsert(self, table, rows, on_conflict, ignore=False):
        t = self.tables.setdefault(table, {})
        for r in rows:
            r = dict(r)
            k = self._key(table, r)
            if k in t and ignore:
                continue
            if k in t:
                t[k].update(r)
            else:
                t[k] = r
        return len(rows)

    def rows(self, table: str) -> list[dict]:
        return list(self.tables.get(table, {}).values())

    def select(self, table, query):  # 아주 작은 필터 해석기(eq/gte/not.is.null/order)
        rows = self.rows(table)
        for part in query.split("&"):
            if "=" not in part:
                continue
            k, v = part.split("=", 1)
            if k in ("select", "limit"):
                continue
            if k == "order":
                col, _, d = v.partition(".")
                rows.sort(key=lambda r: str(r.get(col)), reverse=(d == "desc"))
                continue
            if v.startswith("eq."):
                rows = [r for r in rows if str(r.get(k)) == v[3:]]
            elif v.startswith("gte."):
                rows = [r for r in rows if str(r.get(k)) >= v[4:]]
            elif v == "not.is.null":
                rows = [r for r in rows if r.get(k) is not None]
        return [dict(r) for r in rows]

    def patch(self, table, query, data):
        for r in self.select(table, query):
            k = self._key(table, r)
            self.tables[table][k].update(data)


def api_call_row(op: str, status: str, ms: int, params: dict | None = None) -> dict:
    return {"ts": now_kst().isoformat(), "op": op, "status": status, "ms": ms, "params": params or {}}


def day_start_iso(dt: datetime | None = None) -> str:
    d = (dt or now_kst()).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.isoformat()


def hour_ago_iso(dt: datetime | None = None) -> str:
    return ((dt or now_kst()) - timedelta(hours=1)).isoformat()
