#!/usr/bin/env python3
"""
WordPress 카테고리 생성 + 네비게이션 메뉴 정리
"""
import os, json, sys, base64

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")

if not all([WP_URL, WP_USER, WP_PASS]):
    print("ERROR: WP_URL, WP_USERNAME, WP_APP_PASSWORD 환경변수 필요")
    sys.exit(1)

import requests

cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {cred}",
    "Content-Type": "application/json",
    "User-Agent": "AutoBlog/1.0",
}
API = f"{WP_URL}/wp-json/wp/v2"

# ── 1. 카테고리 확인/생성 ──
TARGET_CATEGORIES = [
    {"name": "AI 도구 & 활용", "slug": "ai-tools", "description": "AI 도구 리뷰, 활용법, 자동화 팁"},
    {"name": "정부지원 & 혜택", "slug": "gov-support", "description": "정부 보조금, 지원금, 숨은 혜택 정보"},
    {"name": "행사 & 컨퍼런스", "slug": "events", "description": "IT, 비즈니스, 산업별 행사 및 컨퍼런스"},
    {"name": "핫 뉴스", "slug": "hot-news", "description": "지금 알아야 할 핫한 뉴스와 트렌드"},
    {"name": "재테크 & 투자", "slug": "finance", "description": "돈 버는 법, 절세, 투자 전략, 부동산"},
    {"name": "교육 & 생산성", "slug": "education", "description": "자기계발, 생산성 도구, 온라인 교육"},
]

print("=== 카테고리 확인/생성 ===")
cat_ids = {}
for cat in TARGET_CATEGORIES:
    resp = requests.get(f"{API}/categories", params={"slug": cat["slug"]}, headers=HEADERS, timeout=10)
    existing = resp.json()
    if existing and len(existing) > 0:
        cat_ids[cat["slug"]] = existing[0]["id"]
        print(f"  [OK] {cat['name']} (id={existing[0]['id']})")
    else:
        resp = requests.post(f"{API}/categories", headers=HEADERS, json=cat, timeout=10)
        if resp.status_code == 201:
            cat_ids[cat["slug"]] = resp.json()["id"]
            print(f"  [NEW] {cat['name']} (id={resp.json()['id']})")
        else:
            print(f"  [ERR] {cat['name']}: {resp.status_code}")

# ── 2. 기존 메뉴 아이템 전부 삭제 ──
print("\n=== 기존 메뉴 아이템 정리 ===")
MENU_ID = 3  # Main Menu

items_resp = requests.get(
    f"{API}/menu-items", params={"menus": MENU_ID, "per_page": 100},
    headers=HEADERS, timeout=10
)

if items_resp.status_code == 200:
    old_items = items_resp.json()
    print(f"  기존 아이템: {len(old_items)}개 → 전부 삭제")
    for item in old_items:
        del_resp = requests.delete(
            f"{API}/menu-items/{item['id']}?force=true",
            headers=HEADERS, timeout=10
        )
        status = "OK" if del_resp.status_code in (200, 204) else f"ERR({del_resp.status_code})"
        print(f"    삭제 [{item['id']}] {item.get('title', {}).get('rendered', '?')[:30]} → {status}")
else:
    print(f"  메뉴 아이템 조회 실패: {items_resp.status_code}")

# ── 3. 새 메뉴 아이템 생성 (홈 + 6 카테고리) ──
print("\n=== 새 메뉴 생성 ===")

NEW_MENU = [
    {"title": "홈", "url": WP_URL + "/", "status": "publish", "menus": MENU_ID, "type": "custom", "menu_order": 1},
]

for i, cat in enumerate(TARGET_CATEGORIES, start=2):
    slug = cat["slug"]
    if slug in cat_ids:
        NEW_MENU.append({
            "title": cat["name"],
            "url": f"{WP_URL}/category/{slug}/",
            "status": "publish",
            "menus": MENU_ID,
            "type": "taxonomy",
            "object": "category",
            "object_id": cat_ids[slug],
            "menu_order": i,
        })

for item in NEW_MENU:
    resp = requests.post(f"{API}/menu-items", headers=HEADERS, json=item, timeout=10)
    if resp.status_code == 200:
        print(f"  [OK] {item['title']} (order={item['menu_order']}, id={resp.json()['id']})")
    else:
        # custom type fallback
        item_fallback = {
            "title": item["title"],
            "url": item["url"],
            "status": "publish",
            "menus": MENU_ID,
            "type": "custom",
            "menu_order": item["menu_order"],
        }
        resp2 = requests.post(f"{API}/menu-items", headers=HEADERS, json=item_fallback, timeout=10)
        if resp2.status_code == 200:
            print(f"  [OK-fallback] {item['title']} (id={resp2.json()['id']})")
        else:
            print(f"  [ERR] {item['title']}: {resp.status_code} / fallback: {resp2.status_code}")
            print(f"    {resp.text[:200]}")

# ── 4. 최종 확인 ──
print("\n=== 최종 메뉴 확인 ===")
final_resp = requests.get(
    f"{API}/menu-items", params={"menus": MENU_ID, "per_page": 50},
    headers=HEADERS, timeout=10
)
if final_resp.status_code == 200:
    items = sorted(final_resp.json(), key=lambda x: x.get("menu_order", 0))
    for item in items:
        title = item.get("title", {}).get("rendered", "?")
        print(f"  [{item['menu_order']}] {title}")
    print(f"\n메뉴 아이템 {len(items)}개 설정 완료!")
else:
    print(f"  확인 실패: {final_resp.status_code}")

print("\n완료!")
