"""수집 — 베스트카테고리/골드박스(매시간) + 관찰 키워드 검색(일 1회) → 스냅샷 UPSERT."""
from __future__ import annotations

import logging
from datetime import datetime

from .core import Store, TimeBudget, now_kst

log = logging.getLogger("deals.snapshot")


def ts_hour(dt: datetime | None = None) -> str:
    return (dt or now_kst()).strftime("%Y-%m-%dT%H:00:00+09:00")


def to_rows(products: list[dict], seen_at: datetime) -> tuple[list[dict], list[dict]]:
    """(product rows, snapshot rows). product_id·price 없는 건 버린다(계측은 호출자)."""
    prods, snaps = [], []
    for p in products:
        pid, price = p.get("product_id"), p.get("price")
        if not pid or not price:
            continue
        prods.append({
            "product_id": pid, "name": p.get("name"), "category": p.get("category"),
            "url": p.get("url"), "image": p.get("image"),
            "last_seen_at": seen_at.isoformat(), "source": p.get("source"),
        })
        snaps.append({
            "product_id": pid, "ts": seen_at.isoformat(), "ts_hour": ts_hour(seen_at),
            "price": int(price), "discount_rate": p.get("discount_rate"),
            "rocket": p.get("rocket"), "rank": p.get("rank"), "source": p.get("source"),
        })
    return prods, snaps


def collect(client, store: Store, cfg: dict, tb: TimeBudget, mode: str = "hourly") -> dict:
    """mode='hourly' → 베스트카테고리+골드박스 / 'daily' → 관찰 키워드 검색까지."""
    col = cfg["collection"]
    seen = now_kst()
    stats = {"products": 0, "snapshots": 0, "dropped": 0, "ops": []}
    batch: list[dict] = []

    for cat in col.get("best_categories", []):
        tb.check_hard()
        if tb.soft_hit():
            log.warning("soft time budget hit — 수집 조기 종료(다음 실행이 이어받는다)")
            break
        try:
            raw = client.bestcategory(cat["id"], col.get("best_limit", 100))
        except Exception as e:
            log.warning("bestcategory %s 실패: %s", cat["id"], e)
            continue
        batch += [client.map_product(r, "bestcategory", cat.get("name", "")) for r in raw]
        stats["ops"].append(f"best:{cat['id']}:{len(raw)}")

    if col.get("goldbox") and not tb.soft_hit():
        try:
            raw = client.goldbox()
            batch += [client.map_product(r, "goldbox") for r in raw]
            stats["ops"].append(f"goldbox:{len(raw)}")
        except Exception as e:
            log.warning("goldbox 실패: %s", e)

    if mode == "daily":
        for kw in col.get("watch_keywords", []):
            tb.check_hard()
            if tb.soft_hit():
                break
            try:
                raw = client.search(kw, col.get("search_limit", 20))
            except Exception as e:
                log.warning("search %s 실패: %s", kw, e)
                continue
            batch += [client.map_product(r, "search", kw) for r in raw]
            stats["ops"].append(f"search:{kw}:{len(raw)}")

    stats["dropped"] = sum(1 for p in batch if not p.get("product_id") or not p.get("price"))
    prods, snaps = to_rows(batch, seen)
    # 같은 실행 안에서 같은 (product_id, ts_hour)가 중복되면 마지막 것만 — DB UNIQUE와 같은 의미론
    prods = list({p["product_id"]: p for p in prods}.values())
    snaps = list({(s["product_id"], s["ts_hour"]): s for s in snaps}.values())
    store.upsert("deal_products", prods, "product_id")
    store.upsert("deal_price_snapshots", snaps, "product_id,ts_hour")
    stats["products"], stats["snapshots"] = len(prods), len(snaps)
    return stats
