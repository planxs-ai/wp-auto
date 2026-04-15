#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WordPress 본문에서 AI 환각 hex/코드 오염 제거 (최소 침습)."""
import os, sys, re, base64, time

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
LIMIT = int(os.environ.get("LIMIT", "0")) or None
STATUS = os.environ.get("STATUS", "publish")

if not all([WP_URL, WP_USER, WP_PASS]):
    print("ERROR: WP_URL, WP_USERNAME, WP_APP_PASSWORD env var required")
    sys.exit(1)

import requests

cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {
    "Authorization": "Basic " + cred,
    "Content-Type": "application/json",
    "User-Agent": "AutoBlog-Cleanup/1.0",
}
API = WP_URL + "/wp-json/wp/v2"


def sanitize_content(content):
    if not content:
        return None
    original = content

    # 1) "고유 XX 코드 <hex>" 류 환각 문구
    content = re.sub(
        r'고유\s*(데이터|식별|분석|고객|사용자|프로필|유저)\s*코드\s*[:\uff1a]?\s*[0-9a-f]{10,}[을를이가은는]?\s*',
        '', content, flags=re.IGNORECASE)

    # 2) 괄호/대괄호 안 hex **먼저** 제거 (순서 중요: 빈 괄호 방지)
    content = re.sub(r'\(\s*[0-9a-f]{10,}\s*\)', '', content)
    content = re.sub(r'\[\s*[0-9a-f]{10,}\s*\]', '', content)

    # 3) 단독 12자리+ hex 제거 (URL/클래스/color hex는 앞뒤 #,-,/,\w로 보호)
    content = re.sub(r'(?<![#\-/\w])[0-9a-f]{12,}(?![\w\-/])', '', content)

    # 4) UUID 형식
    content = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', '', content)

    # 5) 한/영 단어 앞 2칸+ 공백만 1칸으로 (HTML 들여쓰기는 건드리지 않음)
    content = re.sub(r'  +([가-힣a-zA-Z])', r' \1', content)

    return content if content != original else None


def fetch_all_posts():
    posts = []
    page = 1
    while True:
        resp = requests.get(
            API + "/posts",
            params={"per_page": 100, "page": page, "status": STATUS, "context": "edit"},
            headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print("  WARN page", page, "status", resp.status_code)
            print("  body:", resp.text[:300])
            break
        batch = resp.json()
        if not batch or not isinstance(batch, list):
            break
        posts.extend(batch)
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        print("  page", page, "/", total_pages, "-", len(batch), "loaded")
        page += 1
        if page > total_pages:
            break
        if LIMIT and len(posts) >= LIMIT:
            break
    return posts[:LIMIT] if LIMIT else posts


def update_post_content(post_id, new_content):
    resp = requests.post(
        API + "/posts/" + str(post_id),
        headers=HEADERS,
        json={"content": new_content},
        timeout=30)
    return resp.status_code == 200, resp.text[:200]


def preview_diff(original, cleaned, context=40):
    import difflib
    diffs = []
    matcher = difflib.SequenceMatcher(None, original, cleaned)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or len(diffs) >= 3:
            continue
        before = original[max(0, i1 - context):i2 + context].replace("\n", " ")
        after = cleaned[max(0, j1 - context):j2 + context].replace("\n", " ")
        diffs.append((before, after))
    return diffs


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print("=== Content hex cleanup [" + mode + "] ===")
    print("  site:", WP_URL)
    print("  status:", STATUS)
    if LIMIT:
        print("  limit:", LIMIT)
    print()
    print("Loading posts...")
    posts = fetch_all_posts()
    print("Total:", len(posts), "posts\n")

    dirty = 0
    fixed = 0
    errors = 0

    for post in posts:
        pid = post.get("id")
        title_obj = post.get("title", {})
        title = title_obj.get("rendered", "") if isinstance(title_obj, dict) else ""
        content_obj = post.get("content", {})
        if isinstance(content_obj, dict):
            raw = content_obj.get("raw") or content_obj.get("rendered", "")
        else:
            raw = ""
        cleaned = sanitize_content(raw)
        if cleaned is not None:
            dirty += 1
            print("[" + str(pid) + "]", title[:60])
            if not DRY_RUN:
                ok, err = update_post_content(pid, cleaned)
                if ok:
                    fixed += 1
                    print("  => FIXED")
                else:
                    errors += 1
                    print("  => ERROR:", err)
                time.sleep(0.3)
            else:
                for before, after in preview_diff(raw, cleaned)[:1]:
                    print("  - before: ..." + before[:80] + "...")
                    print("  + after:  ..." + after[:80] + "...")
                print("  => (dry run)")

    print()
    print("=== RESULT ===")
    print("  total   :", len(posts))
    print("  dirty   :", dirty)
    if not DRY_RUN:
        print("  fixed   :", fixed)
        print("  errors  :", errors)
    else:
        print("  (dry run - no changes)")


if __name__ == "__main__":
    main()
