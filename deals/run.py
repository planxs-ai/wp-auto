#!/usr/bin/env python3
"""deals CLI — 수집·감지·발행·자체점검.

  python -m deals.run snapshot --mode hourly     # 베스트카테고리+골드박스
  python -m deals.run snapshot --mode daily      # + 관찰 키워드 검색
  python -m deals.run publish  [--dry-run]       # 감지 → 텔레그램·WP 발행
  python -m deals.run selftest                   # API·DB 0콜 (감지기·고지문·멱등 검증)
  python -m deals.run report                     # 최근 실행·수집 현황

status: OK(완주) / PARTIAL(시간·예산으로 중단) / UPSTREAM_DOWN(쿠팡 접속 불가) / ABORTED(외부 취소)
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import uuid
from datetime import timedelta

from . import __version__
from .core import (Budget, BudgetExceeded, CircuitBreaker, MemoryStore, Store, TimeBudget,
                   TimeBudgetExceeded, UpstreamDown, day_start_iso, hour_ago_iso, load_config, now_kst)
from .coupang_client import CoupangClient
from .detector import judge
from .publish import (DisclosureError, ForbiddenPhraseError, TelegramPublisher, WordPressPublisher,
                      deal_headline, telegram_text, wp_html)
from .snapshot import collect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("deals.run")


class Aborted(BaseException):
    """외부 취소(SIGTERM). BaseException이라 재시도 루프의 except Exception이 삼키지 못한다."""


def _install_signals():
    def handler(signum, _frame):
        raise Aborted(f"signal {signum}")
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, handler)


def start_run(store: Store, mode: str) -> str:
    run_id = uuid.uuid4().hex[:16]
    store.upsert("deal_runs", [{"run_id": run_id, "mode": mode, "started_at": now_kst().isoformat(),
                                "status": "RUNNING", "version": __version__}], "run_id")
    return run_id


def finish_run(store: Store, run_id: str, status: str, stats: dict, note: str = "") -> None:
    store.patch("deal_runs", f"run_id=eq.{run_id}", {
        "finished_at": now_kst().isoformat(), "status": status,
        "calls": stats.get("calls", 0), "errors_count": stats.get("errors", 0),
        "items": stats.get("snapshots", stats.get("published", 0)), "note": note[:1000], "stats": stats,
    })


def _event(pid: str, v, day: str, channel: str, msg_id: str | None, link: str) -> dict:
    return {"product_id": pid, "kind": v.kind, "ts_day": day, "ts": now_kst().isoformat(),
            "channel": channel, "msg_id": msg_id, "price": v.price, "low_prev": v.low_prev,
            "high_prev": v.high_prev, "history_days": v.history_days, "deeplink": link}


def build_client(cfg, store, dry=False):
    b = cfg["budget"]
    budget = Budget(b["daily_call_budget"], b.get("hourly", {}))
    used_today = store.calls_since(day_start_iso())
    used_hour = {op: store.calls_since(hour_ago_iso(), op) for op in b.get("hourly", {})}
    budget.preflight(used_today, used_hour)
    log.info("예산 preflight: 오늘 %d/%d 사용, 시간당 %s", used_today, b["daily_call_budget"], used_hour)
    breaker = CircuitBreaker(cfg["api"].get("circuit_breaker_failures", 3))
    return CoupangClient(cfg, store, budget, breaker, dry=dry)


def cmd_snapshot(args, cfg, store) -> int:
    tb = TimeBudget(cfg["runtime"]["soft_minutes"], cfg["runtime"]["hard_minutes"])
    run_id, status, note = start_run(store, f"snapshot:{args.mode}"), "OK", ""
    stats: dict = {}
    try:
        client = build_client(cfg, store)
        stats = collect(client, store, cfg, tb, args.mode)
        stats.update(calls=client.calls, errors=client.errors)
        if tb.soft_hit():
            note = "soft_time_stop"
    except UpstreamDown as e:
        status, note = "UPSTREAM_DOWN", str(e)
        log.error("쿠팡 API 접속 불가 — 중단: %s", e)
    except BudgetExceeded as e:
        status, note = "PARTIAL", str(e)
        log.warning("예산 소진: %s", e)
    except TimeBudgetExceeded as e:
        status, note = "PARTIAL", str(e)
    except Aborted as e:
        finish_run(store, run_id, "ABORTED", stats, str(e))
        raise
    except Exception as e:                      # 예상 못 한 예외도 RUNNING으로 남기지 않는다
        finish_run(store, run_id, "PARTIAL", stats, f"unhandled: {e}")
        log.exception("snapshot 실패")
        return 1
    finish_run(store, run_id, status, stats, note)
    log.info("snapshot %s %s %s", args.mode, status, stats)
    return 0 if status in ("OK", "PARTIAL") else 1


def cmd_publish(args, cfg, store) -> int:
    tb = TimeBudget(cfg["runtime"]["soft_minutes"], cfg["runtime"]["hard_minutes"])
    dcfg, pcfg = cfg["detector"], cfg["publish"]
    run_id, status, note = start_run(store, "publish"), "OK", ""
    stats = {"candidates": 0, "verdicts": 0, "published": 0, "skipped_cap": 0,
             "skipped_dupe": 0, "blocked_rule": 0, "calls": 0, "errors": 0}
    today = now_kst().date().isoformat()
    try:
        since = (now_kst() - timedelta(hours=6)).isoformat()
        latest = store.select("deal_price_snapshots",
                              f"select=product_id,ts,price,discount_rate&ts=gte.{since}&order=ts.desc")
        seen, current = set(), []
        for row in latest:                       # 상품별 최신 스냅샷 1건
            if row["product_id"] in seen:
                continue
            seen.add(row["product_id"])
            current.append(row)
        stats["candidates"] = len(current)

        tg_left = pcfg["daily_cap"]["telegram"] - store.published_today("telegram")
        wp_left = pcfg["daily_cap"]["wordpress"] - store.published_today("wordpress")
        client = build_client(cfg, store) if not args.dry_run else None
        tg = TelegramPublisher(cfg) if pcfg["telegram"]["enabled"] else None
        wp = WordPressPublisher(cfg) if pcfg["wordpress"]["enabled"] else None

        for cur in current:
            tb.check_hard()
            if tb.soft_hit() or (tg_left <= 0 and wp_left <= 0):
                break
            pid = cur["product_id"]
            hist = [h for h in store.price_history(pid, dcfg["full_window_days"]) if h["ts"] < cur["ts"]]
            v = judge(hist, cur, now_kst(), dcfg)
            if not v:
                continue
            stats["verdicts"] += 1
            if store.recent_events(pid, v.kind, dcfg["dedupe_days"]):
                stats["skipped_dupe"] += 1
                continue
            prod = (store.select("deal_products", f"select=product_id,name,url,category&product_id=eq.{pid}") or [{}])[0]
            if args.dry_run:
                log.info("[dry-run] %s", deal_headline(v, prod.get("name", pid)))
                stats["published"] += 1
                continue

            deeplink = prod.get("url", "")
            try:
                dl = client.deeplinks([prod["url"]]) if prod.get("url") else {}
                deeplink = dl.get(prod["url"]) or prod.get("url", "")
            except Exception as e:
                log.warning("deeplink 실패(원본 URL 사용): %s", e)

            wp_id = wp_link = tg_id = None
            try:
                if wp and wp_left > 0:
                    content = wp_html(v, prod, hist + [cur], deeplink, cfg)
                    wp_id, wp_link = wp.publish(deal_headline(v, prod.get("name", "")), content, f"deal-{pid}-{today}")
                    wp_left -= 1
                    store.upsert("deal_events", [_event(pid, v, today, "wordpress", wp_id, deeplink)],
                                 "product_id,kind,ts_day,channel")
                if tg and tg_left > 0:
                    link = wp_link if (pcfg["telegram"]["link_target"] == "wp" and wp_link) else deeplink
                    tg_id = tg.send(telegram_text(v, prod, link, cfg))
                    tg_left -= 1
                    store.upsert("deal_events", [_event(pid, v, today, "telegram", tg_id, link)],
                                 "product_id,kind,ts_day,channel")
            except (DisclosureError, ForbiddenPhraseError) as e:
                stats["blocked_rule"] += 1      # 규칙 위반은 조용히 넘기지 않고 센다
                log.error("발행 규칙 위반으로 차단 %s: %s", pid, e)
                continue
            except Exception as e:
                stats["errors"] += 1
                log.warning("발행 실패 %s: %s", pid, e)
                continue
            if wp_id or tg_id:
                stats["published"] += 1
            else:
                stats["skipped_cap"] += 1
        if client:
            # 덮어쓰기 금지 — 발행 단계에서 센 오류가 API 오류 수에 지워지면 안 된다
            stats["calls"] = client.calls
            stats["errors"] += client.errors
        if tb.soft_hit():
            note = "soft_time_stop"
    except UpstreamDown as e:
        status, note = "UPSTREAM_DOWN", str(e)
    except (BudgetExceeded, TimeBudgetExceeded) as e:
        status, note = "PARTIAL", str(e)
    except Aborted as e:
        finish_run(store, run_id, "ABORTED", stats, str(e))
        raise
    except Exception as e:
        finish_run(store, run_id, "PARTIAL", stats, f"unhandled: {e}")
        log.exception("publish 실패")
        return 1
    finish_run(store, run_id, status, stats, note)
    log.info("publish %s %s", status, stats)
    return 0 if status in ("OK", "PARTIAL") else 1


def cmd_selftest(_args, cfg, _store) -> int:
    """API·DB 0콜. 감지기·고지문·멱등성만 검증한다(정기 실행 통계에 영향 없음)."""
    from datetime import datetime, timedelta as td

    from .core import KST
    from .publish import DisclosureError, assert_compliant
    from .snapshot import to_rows

    now = datetime(2026, 9, 8, 9, 0, tzinfo=KST)
    hist = [{"ts": (now - td(days=d)).isoformat(), "price": 20000, "discount_rate": 5} for d in range(30, 0, -1)]
    v = judge(hist, {"price": 17000, "discount_rate": 20}, now, cfg["detector"])
    assert v and v.kind == "new_low" and not v.full_window, "신저가 판정 실패"
    assert "수집" in v.label and "90일" not in v.label, "이력 30일인데 90일 최저라 표기"
    assert judge(hist[:3], {"price": 100}, now, cfg["detector"]) is None, "이력 부족인데 판정함"

    ms = MemoryStore()
    prods, snaps = to_rows([{"product_id": "1", "price": 1000, "name": "x", "source": "t"}] * 3, now)
    ms.upsert("deal_products", prods, "product_id")
    ms.upsert("deal_price_snapshots", snaps, "product_id,ts_hour")
    ms.upsert("deal_price_snapshots", snaps, "product_id,ts_hour")   # 재실행
    assert len(ms.rows("deal_price_snapshots")) == 1, "멱등성 깨짐"

    try:
        assert_compliant("첫 줄에 고지문 없음\n" + cfg["publish"]["disclosure"], cfg)
        raise AssertionError("고지문 위치 검사 실패")
    except DisclosureError:
        pass
    print(f"selftest OK — 감지기·라벨·멱등·고지문 4항 통과 (v{__version__}, API 0콜)")
    return 0


def cmd_report(_args, _cfg, store) -> int:
    runs = store.select("deal_runs", "select=run_id,mode,started_at,status,calls,errors_count,items,note&order=started_at.desc&limit=10")
    print(f"{'시작':20} {'모드':18} {'상태':14} {'콜':>5} {'오류':>4} {'건수':>6}  note")
    for r in runs:
        print(f"{str(r.get('started_at'))[:19]:20} {r.get('mode',''):18} {r.get('status',''):14} "
              f"{r.get('calls') or 0:5} {r.get('errors_count') or 0:4} {r.get('items') or 0:6}  {(r.get('note') or '')[:40]}")
    prods = store.select("deal_products", "select=product_id&limit=10000")
    snaps = store.select("deal_price_snapshots", f"select=id&ts=gte.{day_start_iso()}&limit=10000")
    print(f"\n추적 상품 {len(prods):,}개 · 오늘 스냅샷 {len(snaps):,}건")
    return 0


def main(argv=None) -> int:
    _install_signals()
    ap = argparse.ArgumentParser(prog="deals")
    ap.add_argument("command", choices=["snapshot", "publish", "selftest", "report"])
    ap.add_argument("--mode", default="hourly", choices=["hourly", "daily"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    store = None if args.command == "selftest" else Store.from_env()
    fn = {"snapshot": cmd_snapshot, "publish": cmd_publish, "selftest": cmd_selftest, "report": cmd_report}[args.command]
    try:
        return fn(args, cfg, store)
    except Aborted as e:
        log.error("외부 취소로 중단: %s", e)
        return 130


if __name__ == "__main__":
    sys.exit(main())
