"""발행 — 텔레그램·워드프레스. 고지문 첫 줄이 없으면 발행 자체를 실패시킨다(§9)."""
from __future__ import annotations

import html
import logging
import os
import re

import requests

from .chart import price_chart_svg
from .detector import Verdict

log = logging.getLogger("deals.publish")


class DisclosureError(RuntimeError):
    pass


class ForbiddenPhraseError(RuntimeError):
    pass


def assert_compliant(text: str, cfg: dict) -> None:
    """고지문이 첫 줄(공정위: 첫 노출 화면)에 있고, 금지 표현이 없어야 한다."""
    disclosure = cfg["publish"]["disclosure"]
    first = (text or "").strip().splitlines()[0] if (text or "").strip() else ""
    plain_first = re.sub(r"<[^>]+>", "", first).strip()
    if disclosure not in plain_first:
        raise DisclosureError("고지문이 첫 줄에 없다 — 발행 중단")
    body = re.sub(r"<[^>]+>", "", text)
    for p in cfg["publish"].get("forbidden_phrases", []):
        if p in body:
            raise ForbiddenPhraseError(f"금지 표현 '{p}' 포함 — 발행 중단")


def deal_headline(v: Verdict, name: str) -> str:
    pct = f"{v.drop_pct:.1f}%" if v.kind == "new_low" else f"할인율 +{(v.discount_rate or 0) - (v.prev_discount_rate or 0):.0f}%p"
    return f"{name} · {v.label} · {v.price:,}원 ({pct}↓)"


def telegram_text(v: Verdict, product: dict, link: str, cfg: dict) -> str:
    d = cfg["publish"]["disclosure"]
    name = html.escape(product.get("name") or "")
    lines = [
        d,
        "",
        f"<b>{name}</b>",
        f"💰 <b>{v.price:,}원</b> · {v.label}",
        f"📉 수집 기간 최저 {v.low_prev:,}원 대비 {v.drop_pct:.1f}%↓ · 최고가 대비 {v.saving_krw:,}원 절약",
        f"🕒 가격 데이터 {v.history_days}일치" + ("" if v.full_window else " (90일 미만 — 기준 기간은 수집 일수)"),
        "",
        f'<a href="{html.escape(link)}">가격 추이 차트 보기</a>',
    ]
    return "\n".join(lines)


def wp_html(v: Verdict, product: dict, history: list[dict], deeplink: str, cfg: dict) -> str:
    d = cfg["publish"]["disclosure"]
    name = html.escape(product.get("name") or "")
    pts = [(str(h["ts"]), int(h["price"])) for h in history if h.get("price")]
    svg = price_chart_svg(pts, title=f"{product.get('name','')} 가격 추이",
                          note=f"수집 {v.history_days}일치 · 출처 쿠팡 파트너스 API")
    window = "90일" if v.full_window else f"수집 {v.history_days}일"
    return (
        f'<p class="deal-disclosure">{d}</p>\n'
        f"<h2>{name} — {v.label}</h2>\n"
        f'<div class="deal-chart">{svg}</div>\n'
        "<table><tbody>"
        f"<tr><th>오늘 가격</th><td>{v.price:,}원</td></tr>"
        f"<tr><th>{window} 최저</th><td>{min(v.low_prev, v.price):,}원</td></tr>"
        f"<tr><th>{window} 최고</th><td>{v.high_prev:,}원</td></tr>"
        f"<tr><th>최고가 대비 절약액</th><td>{v.saving_krw:,}원</td></tr>"
        f"<tr><th>가격 데이터</th><td>{v.history_days}일치 (매시간 수집)</td></tr>"
        "</tbody></table>\n"
        f'<p><a href="{html.escape(deeplink)}" rel="nofollow sponsored noopener" target="_blank">쿠팡에서 현재 가격 확인하기</a></p>\n'
        "<p class=\"deal-note\">가격은 수시로 바뀝니다. 표시 가격은 마지막 수집 시각 기준이며, 구매 전 쿠팡 페이지에서 다시 확인하세요.</p>"
    )


class TelegramPublisher:
    def __init__(self, cfg: dict, token: str | None = None, chat_id: str | None = None,
                 session: requests.Session | None = None):
        self.cfg = cfg
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
        self.s = session or requests.Session()

    def send(self, text: str) -> str:
        assert_compliant(text, self.cfg)
        if not self.token or not self.chat_id:
            raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID 환경변수가 없다")
        r = self.s.post(f"https://api.telegram.org/bot{self.token}/sendMessage",
                        json={"chat_id": self.chat_id, "text": text,
                              "parse_mode": self.cfg["publish"]["telegram"].get("parse_mode", "HTML"),
                              "disable_web_page_preview": False}, timeout=20)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError(f"telegram 실패: {str(data)[:200]}")
        return str(data["result"]["message_id"])


class WordPressPublisher:
    def __init__(self, cfg: dict, url: str | None = None, user: str | None = None,
                 app_password: str | None = None, session: requests.Session | None = None):
        self.cfg = cfg
        self.url = (url or os.environ.get("WP_URL", "")).rstrip("/")
        self.auth = (user or os.environ.get("WP_USERNAME", ""), app_password or os.environ.get("WP_APP_PASSWORD", ""))
        self.s = session or requests.Session()

    def publish(self, title: str, content: str, slug: str) -> tuple[str, str]:
        assert_compliant(content, self.cfg)
        if not self.url or not all(self.auth):
            raise RuntimeError("WP_URL / WP_USERNAME / WP_APP_PASSWORD 환경변수가 없다")
        wp = self.cfg["publish"]["wordpress"]
        payload = {"title": title, "content": content, "slug": slug, "status": wp.get("status", "draft")}
        if wp.get("noindex"):
            payload["meta"] = {wp.get("rank_math_robots_meta", "rank_math_robots"): "noindex,nofollow"}
        r = self.s.post(f"{self.url}/wp-json/wp/v2/posts", json=payload, auth=self.auth, timeout=40)
        if r.status_code >= 300:
            raise RuntimeError(f"wordpress {r.status_code}: {r.text[:300]}")
        data = r.json()
        return str(data.get("id")), data.get("link", "")
