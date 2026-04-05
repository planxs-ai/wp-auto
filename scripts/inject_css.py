#!/usr/bin/env python3
"""
WordPress 커스텀 CSS 주입
방법 1: Customizer API (wp_customize)
방법 2: 기존 custom_css 포스트 직접 수정 (wpdb)
방법 3: 수동 안내 + CSS 파일 생성
"""
import os, sys, base64, json

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

# CSS는 custom_theme.css에서 읽기 (단일 소스)
_css_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_theme.css")
with open(_css_file, "r", encoding="utf-8") as f:
    CUSTOM_CSS = f.read().strip()


def inject_css():
    """WordPress에 커스텀 CSS 주입"""
    api = f"{WP_URL}/wp-json/wp/v2"
    domain = WP_URL.replace("https://", "").replace("http://", "")
    print(f"=== CSS 주입 ({domain}) ===")

    # 테마 확인
    resp = requests.get(f"{api}/themes", headers=HEADERS, timeout=10)
    active_theme = ""
    if resp.status_code == 200:
        for t in resp.json():
            if t.get("status") == "active":
                active_theme = t.get("stylesheet", "")
                print(f"  활성 테마: {active_theme}")
                break

    # 방법: WordPress XML-RPC로 custom_css 업데이트
    print(f"\n  XML-RPC로 custom_css 업데이트 시도...")
    import xmlrpc.client
    try:
        wp = xmlrpc.client.ServerProxy(f"{WP_URL}/xmlrpc.php")

        # custom_css 포스트 검색
        posts = wp.wp.getPosts(0, WP_USER, WP_PASS, {
            "post_type": "custom_css",
            "number": 10,
        })

        css_post = None
        for p in posts:
            if p.get("post_name") == active_theme or p.get("post_type") == "custom_css":
                css_post = p
                break

        if css_post:
            # 업데이트
            result = wp.wp.editPost(0, WP_USER, WP_PASS, css_post["post_id"], {
                "post_content": CUSTOM_CSS,
                "post_status": "publish",
            })
            if result:
                print(f"  [OK] custom_css 업데이트 완료 (id={css_post['post_id']})")
                print(f"\n  CSS 크기: {len(CUSTOM_CSS)} bytes")
                return True
        else:
            # 새로 생성
            new_id = wp.wp.newPost(0, WP_USER, WP_PASS, {
                "post_type": "custom_css",
                "post_name": active_theme,
                "post_content": CUSTOM_CSS,
                "post_status": "publish",
                "post_title": active_theme,
            })
            if new_id:
                print(f"  [OK] custom_css 생성 완료 (id={new_id})")
                print(f"\n  CSS 크기: {len(CUSTOM_CSS)} bytes")
                return True

    except Exception as e:
        err = str(e)
        if "XML-RPC" in err or "403" in err:
            print(f"  XML-RPC 비활성화: {err[:100]}")
        else:
            print(f"  XML-RPC 실패: {err[:100]}")

    # 폴백: 안내
    print(f"\n  [수동 적용 필요]")
    print(f"  1. {WP_URL}/wp-admin/customize.php 접속")
    print(f"  2. '추가 CSS' 클릭")
    print(f"  3. custom_theme.css 내용 붙여넣기 ({len(CUSTOM_CSS)} bytes)")
    print(f"  CSS 파일: {css_file}")
    return False


if __name__ == "__main__":
    inject_css()
