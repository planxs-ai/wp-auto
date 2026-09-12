"""deals 회귀 기준선 — API·DB 0콜. `python -m pytest tests -q`

collect.yml/publish.yml/deals.yml 어디에도 넣지 않는다(테스트 실패가 수집 중단이 되면 안 된다).
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deals.core import (KST, Budget, BudgetExceeded, CircuitBreaker, MemoryStore, TimeBudget,
                        UpstreamDown, load_config)
from deals.coupang_client import CoupangClient, sign, signed_date
from deals.detector import judge
from deals.publish import (DisclosureError, ForbiddenPhraseError, assert_compliant, telegram_text,
                           wp_html)
from deals.snapshot import to_rows, ts_hour

NOW = datetime(2026, 9, 8, 9, 30, tzinfo=KST)


@pytest.fixture
def cfg():
    return load_config()


def hist(days: int, price: int = 20000, discount=None, end=NOW):
    return [{"ts": (end - timedelta(days=d)).isoformat(), "price": price, "discount_rate": discount}
            for d in range(days, 0, -1)]


# ── 서명 ──
def test_sign_format():
    auth = sign("secret", "AK", "GET", "/v2/x", "limit=10", datetime(2026, 9, 8, 0, 1, 2, tzinfo=KST))
    assert auth.startswith("CEA algorithm=HmacSHA256, access-key=AK, signed-date=")
    assert ", signature=" in auth and len(auth.split("signature=")[1]) == 64


def test_signed_date_is_utc_compact():
    sd = signed_date(datetime(2026, 9, 8, 9, 0, 0, tzinfo=KST))   # KST 09:00 → UTC 00:00
    assert sd == "260908T000000Z"


def test_sign_changes_with_query():
    t = datetime(2026, 9, 8, tzinfo=KST)
    assert sign("s", "a", "GET", "/p", "x=1", t) != sign("s", "a", "GET", "/p", "x=2", t)


# ── 예산 ──
def test_daily_budget_blocks():
    b = Budget(3, {})
    for _ in range(3):
        b.take("search")
    with pytest.raises(BudgetExceeded):
        b.take("search")


def test_hourly_budget_is_per_operation():
    b = Budget(100, {"search": 2, "goldbox": 5})
    b.take("search"); b.take("search")
    with pytest.raises(BudgetExceeded):
        b.take("search")
    b.take("goldbox")          # 다른 오퍼레이션은 살아 있다


def test_preflight_counts_db_usage():
    """프로세스 지역 카운터만 믿으면 잡을 쪼갤 때 예산이 두 배가 된다(bid S5 교훈)."""
    b = Budget(10, {"search": 5})
    b.preflight(used_today=9, used_hour={"search": 5})
    assert b.remaining_today() == 1 and b.remaining_hour("search") == 0
    with pytest.raises(BudgetExceeded):
        b.take("search")


# ── 서킷브레이커 ──
def test_breaker_trips_after_threshold():
    cb = CircuitBreaker(3)
    cb.fail("ConnectTimeout"); cb.fail("ConnectTimeout")
    with pytest.raises(UpstreamDown):
        cb.fail("ConnectTimeout")


def test_breaker_resets_on_success():
    cb = CircuitBreaker(3)
    cb.fail("x"); cb.fail("x"); cb.ok(); cb.fail("x")
    assert cb.consecutive == 1


# ── 감지기 ──
def test_new_low_detected(cfg):
    v = judge(hist(30), {"price": 17000}, NOW, cfg["detector"])
    assert v and v.kind == "new_low" and v.price == 17000
    assert v.drop_pct == pytest.approx(15.0, abs=0.01) and v.saving_krw == 3000


def test_small_drop_not_a_deal(cfg):
    assert judge(hist(30), {"price": 19500}, NOW, cfg["detector"]) is None


def test_history_shorter_than_min_is_none(cfg):
    assert judge(hist(3), {"price": 1000}, NOW, cfg["detector"]) is None


def test_label_never_claims_90_days_before_90_days(cfg):
    """§9 정직성: 수집 30일차에 '90일 최저'라고 쓰면 안 된다."""
    v = judge(hist(30), {"price": 15000}, NOW, cfg["detector"])
    assert not v.full_window and v.label == "수집 30일차 최저가 갱신" and "90일" not in v.label


def test_label_unlocks_at_full_window(cfg):
    v = judge(hist(95), {"price": 15000}, NOW, cfg["detector"])
    assert v.full_window and v.label == "90일 최저가 갱신"


def test_discount_jump_detected(cfg):
    h = hist(20, 20000, discount=5)
    v = judge(h, {"price": 19800, "discount_rate": 25}, NOW, cfg["detector"])
    assert v and v.kind == "discount_jump"


def test_cheap_product_excluded(cfg):
    assert judge(hist(30, 2000), {"price": 1000}, NOW, cfg["detector"]) is None


# ── 고지문·금지 표현 ──
def test_disclosure_must_be_first_line(cfg):
    d = cfg["publish"]["disclosure"]
    assert_compliant(f"{d}\n본문", cfg)                       # 통과
    with pytest.raises(DisclosureError):
        assert_compliant(f"본문 먼저\n{d}", cfg)               # '더보기' 뒤 = 부적절
    with pytest.raises(DisclosureError):
        assert_compliant("고지문 없음", cfg)


def test_disclosure_allows_html_wrapped_first_line(cfg):
    d = cfg["publish"]["disclosure"]
    assert_compliant(f'<p class="deal-disclosure">{d}</p>\n<h2>제목</h2>', cfg)


def test_forbidden_phrase_blocks_publish(cfg):
    d = cfg["publish"]["disclosure"]
    with pytest.raises(ForbiddenPhraseError):
        assert_compliant(f"{d}\n이건 무조건 최저 가격입니다", cfg)


def test_rendered_outputs_are_compliant(cfg):
    v = judge(hist(30), {"price": 17000}, NOW, cfg["detector"])
    prod = {"product_id": "1", "name": "생수 2L 24개", "url": "https://www.coupang.com/vp/products/1"}
    assert_compliant(telegram_text(v, prod, "https://example.com/deal", cfg), cfg)
    assert_compliant(wp_html(v, prod, hist(30), "https://link.coupang.com/x", cfg), cfg)


def test_wp_html_marks_affiliate_link_sponsored(cfg):
    v = judge(hist(30), {"price": 17000}, NOW, cfg["detector"])
    html = wp_html(v, {"name": "x"}, hist(30), "https://link.coupang.com/x", cfg)
    assert 'rel="nofollow sponsored noopener"' in html


# ── 멱등성 ──
def test_snapshot_upsert_is_idempotent():
    ms = MemoryStore()
    prods, snaps = to_rows([{"product_id": "p1", "price": 1000, "name": "n", "source": "s"}], NOW)
    for _ in range(3):
        ms.upsert("deal_products", prods, "product_id")
        ms.upsert("deal_price_snapshots", snaps, "product_id,ts_hour")
    assert len(ms.rows("deal_products")) == 1 and len(ms.rows("deal_price_snapshots")) == 1


def test_snapshot_natural_key_is_hourly():
    a = ts_hour(datetime(2026, 9, 8, 9, 5, tzinfo=KST))
    b = ts_hour(datetime(2026, 9, 8, 9, 55, tzinfo=KST))
    c = ts_hour(datetime(2026, 9, 8, 10, 5, tzinfo=KST))
    assert a == b != c


def test_events_unique_per_product_kind_day_channel():
    ms = MemoryStore()
    row = {"product_id": "p1", "kind": "new_low", "ts_day": "2026-09-08", "channel": "telegram", "msg_id": "1"}
    ms.upsert("deal_events", [row], "product_id,kind,ts_day,channel")
    ms.upsert("deal_events", [dict(row, msg_id="2")], "product_id,kind,ts_day,channel")
    ms.upsert("deal_events", [dict(row, channel="wordpress")], "product_id,kind,ts_day,channel")
    assert len(ms.rows("deal_events")) == 2       # 채널별 1건씩, 같은 채널 재발행은 중복 아님


def test_rows_without_price_are_dropped():
    prods, snaps = to_rows([{"product_id": "p1", "price": None}, {"product_id": None, "price": 100}], NOW)
    assert prods == [] and snaps == []


# ── 시간 예산 ──
def test_time_budget_soft_then_hard():
    tb = TimeBudget(0, 0)
    assert tb.soft_hit()
    with pytest.raises(Exception):
        tb.check_hard()


def test_config_inequality_soft_lt_hard_lt_job():
    """soft(12) < hard(15) < cmd timeout(17) < job(20) — 하나만 바꾸면 설계가 깨진다."""
    c = load_config()
    assert c["runtime"]["soft_minutes"] < c["runtime"]["hard_minutes"] < 17 < 20


# ── 클라이언트 (네트워크 대역만 가짜) ──
class FakeResp:
    def __init__(self, code=200, payload=None, text=""):
        self.status_code, self._p, self.text = code, payload, text or str(payload)

    def json(self):
        if self._p is None:
            raise ValueError("not json")
        return self._p


class FakeSession:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kw):
        self.calls.append((method, url))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _client(cfg, session, daily=100):
    return CoupangClient(cfg, None, Budget(daily, cfg["budget"]["hourly"]),
                         CircuitBreaker(cfg["api"]["circuit_breaker_failures"]),
                         access_key="AK", secret_key="SK", session=session)


def test_client_maps_envelope_and_counts_calls(cfg):
    payload = {"rCode": "0", "data": [{"productId": 7, "productName": "물티슈", "productPrice": 9900}]}
    c = _client(cfg, FakeSession([FakeResp(200, payload)]))
    items = c.goldbox()
    assert c.map_product(items[0], "goldbox")["product_id"] == "7"
    assert c.calls == 1 and c.errors == 0


def test_client_raises_on_error_rcode(cfg):
    c = _client(cfg, FakeSession([FakeResp(200, {"rCode": "ERROR", "rMessage": "bad"})]))
    with pytest.raises(RuntimeError):
        c.goldbox()
    assert c.errors == 1


def test_client_trips_breaker_on_repeated_5xx(cfg):
    import requests as rq
    c = _client(cfg, FakeSession([rq.ConnectionError(), rq.ConnectionError(), rq.ConnectionError()]))
    with pytest.raises(UpstreamDown):
        c.goldbox()


def test_client_respects_budget_before_network(cfg):
    s = FakeSession([])
    c = _client(cfg, s, daily=0)
    with pytest.raises(BudgetExceeded):
        c.goldbox()
    assert s.calls == []       # 예산이 0이면 네트워크를 아예 건드리지 않는다


# ── publish 통합 (MemoryStore + 가짜 발행기, 네트워크 0) ──
def _seed(ms, pid="p1", days=30, price=20000, today_price=16000, now=NOW):
    ms.upsert("deal_products", [{"product_id": pid, "name": "생수 2L 24개",
                                 "url": "https://www.coupang.com/vp/products/1"}], "product_id")
    rows = []
    for d in range(days, 0, -1):
        t = now - timedelta(days=d)
        rows.append({"product_id": pid, "ts": t.isoformat(), "ts_hour": ts_hour(t), "price": price})
    rows.append({"product_id": pid, "ts": now.isoformat(), "ts_hour": ts_hour(now), "price": today_price})
    ms.upsert("deal_price_snapshots", rows, "product_id,ts_hour")
    return ms


class _Args:
    dry_run = False
    mode = "hourly"


def _run_publish(monkeypatch, ms, cfg, sent):
    import deals.run as R

    class FakeTG:
        def __init__(self, cfg): self.cfg = cfg
        def send(self, text):
            assert_compliant(text, self.cfg)          # 발행 직전 규칙이 실제로 걸리는지
            sent.append(("telegram", text)); return f"tg{len(sent)}"

    class FakeWP:
        def __init__(self, cfg): self.cfg = cfg
        def publish(self, title, content, slug):
            assert_compliant(content, self.cfg)
            sent.append(("wordpress", title)); return f"wp{len(sent)}", "https://deal.example/x"

    class FakeClient:
        calls = errors = 0
        def deeplinks(self, urls): return {u: "https://link.coupang.com/re/x" for u in urls}

    monkeypatch.setattr(R, "TelegramPublisher", FakeTG)
    monkeypatch.setattr(R, "WordPressPublisher", FakeWP)
    monkeypatch.setattr(R, "build_client", lambda *a, **k: FakeClient())
    monkeypatch.setattr(R, "now_kst", lambda: NOW)
    return R.cmd_publish(_Args(), cfg, ms)


def test_publish_end_to_end_writes_events_and_sends(monkeypatch, cfg):
    ms = _seed(MemoryStore())
    sent = []
    assert _run_publish(monkeypatch, ms, cfg, sent) == 0
    assert {c for c, _ in sent} == {"telegram", "wordpress"}
    events = ms.rows("deal_events")
    assert len(events) == 2 and {e["channel"] for e in events} == {"telegram", "wordpress"}
    run = ms.rows("deal_runs")[0]
    assert run["status"] == "OK" and run["stats"]["published"] == 1


def test_publish_is_idempotent_same_day(monkeypatch, cfg):
    """같은 날 두 번 돌려도 같은 딜을 다시 쏘지 않는다(dedupe)."""
    ms = _seed(MemoryStore())
    sent = []
    _run_publish(monkeypatch, ms, cfg, sent)
    _run_publish(monkeypatch, ms, cfg, sent)
    assert len(sent) == 2 and len(ms.rows("deal_events")) == 2
    assert ms.rows("deal_runs")[-1]["stats"]["skipped_dupe"] == 1


def test_publish_skips_when_no_deal(monkeypatch, cfg):
    ms = _seed(MemoryStore(), today_price=19900)      # 하락폭 미달
    sent = []
    _run_publish(monkeypatch, ms, cfg, sent)
    assert sent == [] and ms.rows("deal_events") == []


def test_publish_respects_daily_cap(monkeypatch, cfg):
    ms = MemoryStore()
    for i in range(cfg["publish"]["daily_cap"]["wordpress"] + 3):
        _seed(ms, pid=f"p{i}")
    sent = []
    _run_publish(monkeypatch, ms, cfg, sent)
    wp = [c for c, _ in sent if c == "wordpress"]
    tg = [c for c, _ in sent if c == "telegram"]
    assert len(wp) <= cfg["publish"]["daily_cap"]["wordpress"]
    assert len(tg) <= cfg["publish"]["daily_cap"]["telegram"]


def test_publish_never_leaves_run_stuck_in_running(monkeypatch, cfg):
    """발행기가 터져도 deal_runs에 RUNNING이 남으면 안 된다(bid 잡 고착 교훈)."""
    import deals.run as R
    ms = _seed(MemoryStore())

    class Boom:
        def __init__(self, cfg): pass
        def publish(self, *a): raise RuntimeError("wp 500")
        def send(self, *a): raise RuntimeError("telegram down")

    monkeypatch.setattr(R, "TelegramPublisher", Boom)
    monkeypatch.setattr(R, "WordPressPublisher", Boom)
    monkeypatch.setattr(R, "build_client", lambda *a, **k: type("C", (), {"calls": 0, "errors": 0, "deeplinks": lambda s, u: {}})())
    monkeypatch.setattr(R, "now_kst", lambda: NOW)
    R.cmd_publish(_Args(), cfg, ms)
    run = ms.rows("deal_runs")[0]
    assert run["status"] != "RUNNING" and run["finished_at"] and run["stats"]["errors"] >= 1
    assert ms.rows("deal_events") == []          # 실패한 발행은 이벤트를 남기지 않는다
