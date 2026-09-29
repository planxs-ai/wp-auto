"""급락 감지기 — 순수 함수. 입력은 가격 이력(list of {ts, price, discount_rate}), 출력은 딜 판정.

정직성 규칙(밑그림 §5-D·§7 D+90):
- 기준 기간 = 실제 수집 일수. 이력이 full_window_days 미만이면 "수집 N일차 최저"이지 "90일 최저"가 아니다.
- 이력이 min_history_days 미만이면 판정하지 않는다(None).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Verdict:
    kind: str                 # 'new_low' | 'discount_jump'
    price: int
    low_prev: int             # 오늘 이전 수집 기간 최저가
    high_prev: int            # 오늘 이전 수집 기간 최고가
    drop_pct: float           # 최저가 대비 하락률(양수 = 더 싸짐)
    saving_krw: int           # 최고가 − 오늘가
    history_days: int
    full_window: bool         # history_days >= full_window_days
    discount_rate: float | None = None
    prev_discount_rate: float | None = None

    @property
    def label(self) -> str:
        if self.full_window:
            return "90일 최저가 갱신"
        return f"수집 {self.history_days}일차 최저가 갱신"


def _parse_ts(v) -> datetime:
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def history_days(history: list[dict], now: datetime) -> int:
    """데이터가 실제로 덮는 일수. `now`가 아니라 스냅샷의 첫~마지막 간격으로 센다 —
    마지막 수집이 오래된 상품에 '오늘까지 N일치'라고 말하지 않기 위해서다."""
    if not history:
        return 0
    ts = [_parse_ts(h["ts"]) for h in history]
    return max(1, (max(ts) - min(ts)).days + 1)


def judge(history: list[dict], current: dict, now: datetime, cfg: dict) -> Verdict | None:
    """history: 오늘 이전 스냅샷(가격>0), current: {price, discount_rate}. cfg: config['detector']."""
    price = current.get("price")
    if not price or price < cfg.get("min_price_krw", 0):
        return None
    prior = [h for h in history if h.get("price")]
    days = history_days(prior, now)
    if days < cfg["min_history_days"]:
        return None
    prices = [int(h["price"]) for h in prior]
    low_prev, high_prev = min(prices), max(prices)
    full = days >= cfg["full_window_days"]
    drop_pct = round((low_prev - price) / low_prev * 100, 2) if low_prev else 0.0
    saving = max(0, high_prev - price)

    if price < low_prev and drop_pct >= cfg["min_drop_pct"]:
        return Verdict("new_low", price, low_prev, high_prev, drop_pct, saving, days, full,
                       current.get("discount_rate"), _last_discount(prior))

    dr, prev_dr = current.get("discount_rate"), _last_discount(prior)
    if dr is not None and prev_dr is not None and (float(dr) - float(prev_dr)) >= cfg["discount_jump_pp"]:
        return Verdict("discount_jump", price, low_prev, high_prev, drop_pct, saving, days, full, float(dr), float(prev_dr))
    return None


def _last_discount(history: list[dict]):
    for h in sorted(history, key=lambda x: str(x["ts"]), reverse=True):
        if h.get("discount_rate") is not None:
            return float(h["discount_rate"])
    return None
