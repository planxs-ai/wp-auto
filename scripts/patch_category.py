#!/usr/bin/env python3
"""
patch_category.py — 기존 3days 포스트 카테고리 일괄 패치
=======================================================
카테고리 없는 3days 일일 전략 리포트 포스트에 '재테크 & 투자' (slug: finance-invest) 부여

사용:
  # 환경변수 설정 후 실행
  python scripts/patch_category.py

  # 테스트 (실제 수정 없음)
  python scripts/patch_category.py --dry-run

  # 특정 카테고리로 지정
  python scripts/patch_category.py --category "ETF 시장분석"
"""

import os
import sys
import json
import base64
import argparse
import logging
import html as _html

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("patch-category")

try:
    import requests
except ImportError:
    print("requests 미설치 → pip install requests")
    sys.exit(1)

# ── 환경변수
WP_URL  = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")

# ── 카테고리 slug 맵
CATEGORY_SLUG_MAP = {
    "재테크 & 투자":    "finance-invest",
    "ETF 시장분석":     "etf-analysis",
    "ETF 전략리포트":   "etf-strategy",
    "3days 전략리포트": "3days-strategy",
}

TARGET_CATEGORY = "재테크 & 투자"   # 기본 적용 카테고리
SEARCH_KEYWORD  = "3days"           # 이 키워드가 slug에 포함된 포스트만 패치


def get_headers():
    cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
    return {
        "Authorization": f"Basic {cred}",
        "Content-Type": "application/json",
    }


def get_or_create_category(name: str) -> int | None:
    """slug 기반 1순위 조회 → name 검색 → 신규 생성"""
    headers = get_headers()
    slug = CATEGORY_SLUG_MAP.get(name)

    try:
        # 1순위: slug 조회
        if slug:
            r = requests.get(
                f"{WP_URL}/wp-json/wp/v2/categories",
                headers=headers,
                params={"slug": slug},
                timeout=10,
            )
            cats = r.json() if r.ok else []
            if cats:
                log.info(f"카테고리 확인 (slug): {name} → id={cats[0]['id']}")
                return cats[0]["id"]

        # 2순위: name 검색
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/categories",
            headers=headers,
            params={"search": name, "per_page": 10},
            timeout=10,
        )
        if r.ok:
            for c in r.json():
                if _html.unescape(c["name"]).lower() == name.lower():
                    cat_id = c["id"]
                    # 한국어 slug → 영문 slug 자동 교정
                    if slug and c.get("slug", "").startswith("%"):
                        requests.post(
                            f"{WP_URL}/wp-json/wp/v2/categories/{cat_id}",
                            headers=headers,
                            json={"slug": slug},
                            timeout=10,
                        )
                        log.info(f"카테고리 slug 교정: {name} → {slug}")
                    log.info(f"카테고리 확인 (name): {name} → id={cat_id}")
                    return cat_id

        # 3순위: 신규 생성
        create_data = {"name": name}
        if slug:
            create_data["slug"] = slug
        r = requests.post(
            f"{WP_URL}/wp-json/wp/v2/categories",
            headers=headers,
            json=create_data,
            timeout=10,
        )
        if r.ok:
            cat_id = r.json().get("id")
            log.info(f"카테고리 생성: {name} (slug={slug}) → id={cat_id}")
            return cat_id
        else:
            log.error(f"카테고리 생성 실패: {r.status_code} {r.text[:200]}")

    except Exception as e:
        log.error(f"카테고리 처리 오류: {e}")

    return None


def fetch_all_3days_posts() -> list:
    """3days 키워드가 포함된 포스트 전체 수집 (페이지네이션)"""
    headers = get_headers()
    posts = []
    page = 1

    while True:
        r = requests.get(
            f"{WP_URL}/wp-json/wp/v2/posts",
            headers=headers,
            params={
                "search": SEARCH_KEYWORD,
                "per_page": 100,
                "page": page,
                "status": "publish",
                "_fields": "id,title,slug,categories,link",
            },
            timeout=15,
        )
        if not r.ok:
            log.error(f"포스트 조회 실패: {r.status_code}")
            break

        batch = r.json()
        if not batch:
            break

        posts.extend(batch)
        log.info(f"  페이지 {page}: {len(batch)}개 수집 (누적 {len(posts)}개)")

        total_pages = int(r.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1

    return posts


def patch_post_category(post_id: int, cat_id: int, existing_cats: list) -> bool:
    """포스트에 카테고리 추가 (기존 카테고리 유지)"""
    headers = get_headers()

    if cat_id in existing_cats:
        return False  # 이미 적용됨

    new_cats = list(set(existing_cats + [cat_id]))

    # WordPress REST API: POST 또는 PATCH 둘 다 지원, 명시적으로 PATCH 사용
    r = requests.post(
        f"{WP_URL}/wp-json/wp/v2/posts/{post_id}",
        headers={**headers, "X-HTTP-Method-Override": "PATCH"},
        json={"categories": new_cats},
        timeout=10,
    )
    if not r.ok:
        log.warning(f"    → HTTP {r.status_code}: {r.text[:300]}")
    return r.ok


def main():
    parser = argparse.ArgumentParser(description="3days 포스트 카테고리 일괄 패치")
    parser.add_argument("--dry-run", action="store_true", help="실제 수정 없이 테스트")
    parser.add_argument("--category", default=TARGET_CATEGORY, help="적용할 카테고리명")
    args = parser.parse_args()

    # 인증 정보 체크
    if not WP_URL or not WP_USER or not WP_PASS:
        log.error("환경변수 미설정: WP_URL, WP_USERNAME, WP_APP_PASSWORD 필요")
        log.error("PowerShell 예시:")
        log.error('  $env:WP_URL="https://planx-ai.com"')
        log.error('  $env:WP_USERNAME="admin"')
        log.error('  $env:WP_APP_PASSWORD="xxxx xxxx xxxx"')
        sys.exit(1)

    log.info("=" * 55)
    log.info(f"대상 사이트: {WP_URL}")
    log.info(f"적용 카테고리: {args.category}")
    log.info(f"Dry Run: {args.dry_run}")
    log.info("=" * 55)

    # Step 1: 카테고리 ID 확보
    cat_id = get_or_create_category(args.category)
    if not cat_id:
        log.error("카테고리 ID 확보 실패 — 중단")
        sys.exit(1)
    log.info(f"적용 카테고리 ID: {cat_id}")

    # Step 2: 3days 포스트 전체 수집
    log.info(f"\n'{SEARCH_KEYWORD}' 포스트 수집 중...")
    posts = fetch_all_3days_posts()
    log.info(f"총 {len(posts)}개 포스트 발견\n")

    if not posts:
        log.warning("패치 대상 포스트 없음")
        return

    # Step 3: 카테고리 미적용 포스트 필터
    needs_patch = [p for p in posts if cat_id not in p.get("categories", [])]
    already_set = len(posts) - len(needs_patch)

    log.info(f"이미 카테고리 있음: {already_set}개")
    log.info(f"패치 필요: {len(needs_patch)}개\n")

    if not needs_patch:
        log.info("✅ 모든 포스트에 카테고리가 이미 적용되어 있습니다")
        return

    # Step 4: 패치 실행
    success = 0
    fail = 0

    for p in needs_patch:
        title = p.get("title", {}).get("rendered", p.get("slug", ""))
        post_id = p["id"]
        existing_cats = p.get("categories", [])

        if args.dry_run:
            log.info(f"  [DRY] id={post_id} | {title[:50]}")
            success += 1
            continue

        ok = patch_post_category(post_id, cat_id, existing_cats)
        if ok:
            log.info(f"  ✅ id={post_id} | {title[:50]}")
            success += 1
        else:
            log.warning(f"  ❌ id={post_id} | {title[:50]}")
            fail += 1

    log.info("\n" + "=" * 55)
    if args.dry_run:
        log.info(f"[DRY RUN] 패치 예정: {success}개")
    else:
        log.info(f"완료 — 성공: {success}개 | 실패: {fail}개")
    log.info("=" * 55)


if __name__ == "__main__":
    main()
