#!/usr/bin/env python3
"""
WordPress 카테고리 + 네비게이션 메뉴 설정
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
    {"name": "AI 도구 & 생산성", "slug": "ai-tools", "description": "ChatGPT, Claude, Gemini 등 AI 도구 리뷰, 비교, 활용법과 업무 자동화 팁"},
    {"name": "재테크 & 투자", "slug": "finance-invest", "description": "ETF, 적금, 주식, 부동산 등 실전 투자 전략과 재테크 노하우"},
    {"name": "부업 & 수익화", "slug": "side-income", "description": "블로그 수익화, 직장인 부업, 프리랜서 수익 다각화 방법"},
    {"name": "IT & 테크 리뷰", "slug": "tech-review", "description": "노트북, 스마트 장비, 앱, 소프트웨어 비교 리뷰"},
    {"name": "정부지원 & 절세", "slug": "gov-support", "description": "정부 보조금, 지원사업, 종합소득세, 연말정산 절세 가이드"},
    {"name": "생활 경제", "slug": "life-economy", "description": "보험 비교, 대출 가이드, 생활비 절약, 전월세 팁"},
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

# ── 2. 메뉴 확인 ──
print("\n=== 메뉴 확인 ===")
menus_resp = requests.get(f"{API}/menus", headers=HEADERS, timeout=10)
menu_id = None
if menus_resp.status_code == 200:
    menus = menus_resp.json()
    for m in menus:
        print(f"  메뉴: [{m['id']}] {m['name']}")
        if 'main' in m['name'].lower() or 'primary' in m['name'].lower() or menu_id is None:
            menu_id = m['id']

if not menu_id:
    print("  메뉴를 찾을 수 없습니다.")
    sys.exit(1)

print(f"  사용할 메뉴: ID={menu_id}")

# ── 3. 기존 메뉴 아이템 전부 삭제 (2회 반복으로 확실히) ──
print(f"\n=== 기존 메뉴 아이템 삭제 (메뉴 {menu_id}) ===")
for attempt in range(2):
    items_resp = requests.get(
        f"{API}/menu-items", params={"menus": menu_id, "per_page": 100},
        headers=HEADERS, timeout=10
    )
    if items_resp.status_code == 200:
        old_items = items_resp.json()
        if not old_items:
            print(f"  기존 아이템 없음 — 건너뜀")
            break
        print(f"  {len(old_items)}개 삭제 중... (시도 {attempt+1})")
        for item in old_items:
            del_resp = requests.delete(f"{API}/menu-items/{item['id']}?force=true", headers=HEADERS, timeout=10)
            status = "OK" if del_resp.status_code in (200, 204) else f"ERR:{del_resp.status_code}"
            print(f"    [{status}] id={item['id']} {item.get('title', {}).get('rendered', '')}")
    else:
        print(f"  조회 실패: {items_resp.status_code} — 메뉴 API 미지원일 수 있음")
        break
print("  삭제 완료")

# ── 4. 새 메뉴 아이템 생성 ──
print(f"\n=== 새 메뉴 생성 ===")

# 홈
resp = requests.post(f"{API}/menu-items", headers=HEADERS, json={
    "title": "홈",
    "url": WP_URL + "/",
    "status": "publish",
    "menus": menu_id,
    "type": "custom",
    "menu_order": 1,
}, timeout=10)
print(f"  [{'OK' if resp.status_code in (200, 201) else 'ERR'}] 홈 (status={resp.status_code})")

# 카테고리 아이템
for i, cat in enumerate(TARGET_CATEGORIES, start=2):
    slug = cat["slug"]
    if slug not in cat_ids:
        continue

    # taxonomy 타입으로 시도
    item_data = {
        "title": cat["name"],
        "status": "publish",
        "menus": menu_id,
        "type": "taxonomy",
        "object": "category",
        "object_id": cat_ids[slug],
        "menu_order": i,
    }
    resp = requests.post(f"{API}/menu-items", headers=HEADERS, json=item_data, timeout=10)

    if resp.status_code not in (200, 201):
        # custom 링크로 폴백
        item_data = {
            "title": cat["name"],
            "url": f"{WP_URL}/category/{slug}/",
            "status": "publish",
            "menus": menu_id,
            "type": "custom",
            "menu_order": i,
        }
        resp = requests.post(f"{API}/menu-items", headers=HEADERS, json=item_data, timeout=10)

    print(f"  [{'OK' if resp.status_code in (200, 201) else 'ERR'}] {cat['name']} (order={i})")

# ── 5. 최종 확인 ──
print(f"\n=== 최종 메뉴 (ID={menu_id}) ===")
final = requests.get(
    f"{API}/menu-items", params={"menus": menu_id, "per_page": 50},
    headers=HEADERS, timeout=10
)
if final.status_code == 200:
    items = sorted(final.json(), key=lambda x: x.get("menu_order", 0))
    for item in items:
        title = item.get("title", {}).get("rendered", "?")
        url = item.get("url", "")
        print(f"  [{item['menu_order']}] {title:25s} → {url}")
    print(f"\n총 {len(items)}개 메뉴 아이템")
else:
    print(f"  확인 실패: {final.status_code}")

# ── 6. WP 캐시 클리어 시도 ──
print("\n=== 캐시 클리어 ===")
# wp-json으로 접근 가능한 캐시 퍼지 (플러그인 의존적)
for endpoint in ["/wp-json/wp-super-cache/v1/cache", "/wp-json/wp/v2/settings"]:
    try:
        r = requests.get(f"{WP_URL}{endpoint}", headers=HEADERS, timeout=5)
        if r.status_code == 200:
            print(f"  {endpoint}: 접근 가능")
    except Exception:
        pass

# settings 엔드포인트에 더미 업데이트 (캐시 무효화 트리거)
try:
    r = requests.get(f"{API}/settings", headers=HEADERS, timeout=5)
    if r.status_code == 200:
        settings = r.json()
        # 동일 값으로 업데이트하면 캐시 무효화될 수 있음
        requests.post(f"{API}/settings", headers=HEADERS,
                     json={"title": settings.get("title", "")}, timeout=5)
        print("  설정 터치 (캐시 무효화 시도)")
except Exception:
    pass

print("\n완료! 사이트를 새로고침하세요.")
print("캐시가 남아있다면 WP Admin > 설정에서 캐시를 수동 퍼지하세요.")
