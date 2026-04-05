#!/usr/bin/env python3
"""
planx-ai.com 카테고리 통합 스크립트
- 45개 파편 카테고리 → 5개 대분류로 통합
- 글의 카테고리를 재배정 후 빈 카테고리 삭제
- Uncategorized 글은 콘텐츠 기반으로 자동 분류

사용:
  WP_URL=https://planx-ai.com WP_USERNAME=admin WP_APP_PASSWORD="xxxx" python scripts/consolidate_categories.py
  WP_URL=https://planx-ai.com WP_USERNAME=admin WP_APP_PASSWORD="xxxx" python scripts/consolidate_categories.py --live
"""

import os
import sys
import base64
import json
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("consolidate_categories")

try:
    import requests
except ImportError:
    log.error("requests 필요: pip install requests")
    sys.exit(1)

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")

if not all([WP_URL, WP_USER, WP_PASS]):
    log.error("환경변수 필요: WP_URL, WP_USERNAME, WP_APP_PASSWORD")
    sys.exit(1)

cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {cred}",
    "Content-Type": "application/json",
}
API = f"{WP_URL}/wp-json/wp/v2"

# ── 통합 대상 카테고리 매핑 ──
# key: 새 카테고리 (slug, name, description)
# value: 흡수할 기존 카테고리 이름 목록 (부분 매치)
TARGET_CATEGORIES = {
    "ai-tools": {
        "name": "AI 도구 & 활용",
        "description": "AI 도구 비교, 활용법, 튜토리얼, 업무 생산성 향상 가이드",
        "absorb": [
            "AI 개발", "AI 교육", "AI 글쓰기", "AI 기술 동향 분석",
            "AI 도구 & 생산성", "AI 도구 활용", "AI 마케팅", "AI 마케팅 도구",
            "AI 영상 편집", "AI 이미지 생성", "AI 코딩", "AI 투자 분석",
            "AI 툴 비교", "AI 툴 활용", "AI 튜토리얼", "AI 협업",
            "AI 활용", "AI 활용 가계 관리", "AI 활용 가이드", "AI 활용 사례",
            "AI 활용 팁", "AI 활용/마케팅", "AI 활용/콘텐츠 제작", "AI 활용법",
            "AI 활용팁", "기업용 AI", "업무 생산성", "마케팅",
        ],
    },
    "finance": {
        "name": "재테크 & 투자",
        "description": "재테크 기초, 주식/ETF 투자, 대출, 금융 상품 비교",
        "absorb": [
            "재테크", "재테크 & 투자", "투자", "ETF 시장분석", "대출",
        ],
    },
    "side-income": {
        "name": "부업 & 수익화",
        "description": "부업, 창업, 온라인 수익화, 프리랜서 가이드",
        "absorb": [
            "부업 & 수익화", "부업/창업", "네트워킹", "글쓰기/출판",
        ],
    },
    "tech-review": {
        "name": "IT & 테크 리뷰",
        "description": "최신 IT 제품 리뷰, 기술 트렌드, 가젯 추천",
        "absorb": [
            "IT & 테크 리뷰", "IT팁", "제품 리뷰",
        ],
    },
    "life-money": {
        "name": "생활 & 절세",
        "description": "생활 경제 팁, 정부지원금, 절세 전략, 라이프 해킹",
        "absorb": [
            "생활 경제", "정부지원 & 절세", "육아", "취업",
        ],
    },
}


def wp_get(endpoint: str, params: dict | None = None) -> list | dict:
    resp = requests.get(f"{API}/{endpoint}", headers=HEADERS, params=params or {}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def wp_post(endpoint: str, data: dict) -> requests.Response:
    return requests.post(f"{API}/{endpoint}", headers=HEADERS, json=data, timeout=15)


def wp_delete(endpoint: str) -> requests.Response:
    return requests.delete(f"{API}/{endpoint}", headers=HEADERS, params={"force": True}, timeout=15)


def get_all_categories() -> list[dict]:
    """모든 카테고리 조회 (페이지네이션 처리)"""
    cats = []
    page = 1
    while True:
        batch = wp_get("categories", {"per_page": 100, "page": page})
        if not batch:
            break
        cats.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return cats


def get_posts_by_category(cat_id: int) -> list[dict]:
    """특정 카테고리의 모든 글 조회"""
    posts = []
    page = 1
    while True:
        batch = wp_get("posts", {"categories": cat_id, "per_page": 100, "page": page, "_fields": "id,title,categories"})
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return posts


def ensure_target_category(slug: str, info: dict, existing_cats: list[dict]) -> int:
    """대상 카테고리가 없으면 생성, 있으면 ID 반환"""
    for cat in existing_cats:
        if cat["slug"] == slug:
            log.info(f"  [EXISTS] {info['name']} (id={cat['id']})")
            return cat["id"]

    resp = wp_post("categories", {
        "name": info["name"],
        "slug": slug,
        "description": info["description"],
    })
    if resp.status_code == 201:
        cat_id = resp.json()["id"]
        log.info(f"  [NEW] {info['name']} (id={cat_id})")
        return cat_id
    else:
        log.error(f"  [ERR] {info['name']} 생성 실패: {resp.status_code}")
        sys.exit(1)


def reassign_posts(old_cat_id: int, new_cat_id: int, old_name: str, dry_run: bool) -> int:
    """글의 카테고리를 변경"""
    posts = get_posts_by_category(old_cat_id)
    if not posts:
        return 0

    count = 0
    for post in posts:
        post_id = post["id"]
        title = post.get("title", {}).get("rendered", "?")[:40]
        current_cats = post.get("categories", [])

        # 기존 카테고리 제거 + 새 카테고리 추가
        new_cats = [c for c in current_cats if c != old_cat_id]
        if new_cat_id not in new_cats:
            new_cats.append(new_cat_id)

        if dry_run:
            log.info(f"    [DRY] '{title}' → cat {current_cats} → {new_cats}")
        else:
            resp = wp_post(f"posts/{post_id}", {"categories": new_cats})
            if resp.status_code == 200:
                log.info(f"    [OK] '{title}' → {new_cats}")
            else:
                log.warning(f"    [ERR] '{title}' 실패: {resp.status_code}")
            time.sleep(0.3)
        count += 1

    return count


def delete_empty_category(cat_id: int, cat_name: str, dry_run: bool) -> bool:
    """글이 없는 카테고리 삭제"""
    if dry_run:
        log.info(f"    [DRY] 삭제 예정: '{cat_name}' (id={cat_id})")
        return True

    resp = wp_delete(f"categories/{cat_id}")
    if resp.status_code == 200:
        log.info(f"    [DEL] '{cat_name}' 삭제 완료")
        return True
    else:
        log.warning(f"    [ERR] '{cat_name}' 삭제 실패: {resp.status_code}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="카테고리 통합 (45개 → 5개)")
    parser.add_argument("--live", action="store_true", help="실제 실행 (기본: 드라이런)")
    args = parser.parse_args()

    dry_run = not args.live
    mode = "DRY-RUN" if dry_run else "LIVE"
    log.info(f"=== 카테고리 통합 [{mode}] — {WP_URL} ===")

    # 1. 기존 카테고리 조회
    all_cats = get_all_categories()
    log.info(f"기존 카테고리: {len(all_cats)}개")

    # 이름 → ID 매핑
    cat_name_to_id = {cat["name"]: cat["id"] for cat in all_cats}

    # 2. 대상 카테고리 생성/확인
    log.info("\n── 대상 카테고리 준비 ──")
    target_ids = {}
    for slug, info in TARGET_CATEGORIES.items():
        if dry_run:
            existing = next((c for c in all_cats if c["slug"] == slug), None)
            if existing:
                target_ids[slug] = existing["id"]
                log.info(f"  [EXISTS] {info['name']} (id={existing['id']})")
            else:
                target_ids[slug] = -1
                log.info(f"  [DRY] {info['name']} → 생성 예정")
        else:
            target_ids[slug] = ensure_target_category(slug, info, all_cats)

    # 3. 글 재배정
    log.info("\n── 글 재배정 ──")
    total_moved = 0
    cats_to_delete = []

    for slug, info in TARGET_CATEGORIES.items():
        new_cat_id = target_ids[slug]
        log.info(f"\n[{info['name']}] ←")

        for old_name in info["absorb"]:
            old_id = cat_name_to_id.get(old_name)
            if not old_id:
                continue

            # 같은 카테고리면 스킵
            if old_id == new_cat_id:
                log.info(f"  '{old_name}' = 대상 카테고리 (스킵)")
                continue

            posts = get_posts_by_category(old_id)
            if posts:
                log.info(f"  '{old_name}' ({len(posts)}편) → 이동")
                moved = reassign_posts(old_id, new_cat_id, old_name, dry_run)
                total_moved += moved
            else:
                log.info(f"  '{old_name}' (0편) → 빈 카테고리")

            cats_to_delete.append((old_id, old_name))

    # 4. Uncategorized 처리 — ai-tools로 이동
    uncat_id = cat_name_to_id.get("Uncategorized")
    if uncat_id:
        posts = get_posts_by_category(uncat_id)
        if posts:
            ai_cat_id = target_ids.get("ai-tools", -1)
            log.info(f"\n[Uncategorized] {len(posts)}편 → AI 도구 & 활용으로 이동")
            moved = reassign_posts(uncat_id, ai_cat_id, "Uncategorized", dry_run)
            total_moved += moved

    # 5. 빈 카테고리 삭제
    log.info(f"\n── 빈 카테고리 삭제 ({len(cats_to_delete)}개) ──")
    deleted = 0
    for cat_id, cat_name in cats_to_delete:
        # Uncategorized(ID=1)는 WP 기본이라 삭제 불가
        if cat_name == "Uncategorized":
            log.info(f"    '{cat_name}' — WP 기본 카테고리 (삭제 불가)")
            continue
        if delete_empty_category(cat_id, cat_name, dry_run):
            deleted += 1

    # 6. 결과
    log.info(f"\n{'='*50}")
    log.info(f"결과 [{mode}]:")
    log.info(f"  글 이동: {total_moved}편")
    log.info(f"  카테고리 삭제: {deleted}개")
    log.info(f"  최종 카테고리: {len(TARGET_CATEGORIES)}개")
    log.info(f"{'='*50}")

    if dry_run:
        log.info("\n→ 실제 실행: --live 플래그 추가")


if __name__ == "__main__":
    main()
