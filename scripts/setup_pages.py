#!/usr/bin/env python3
"""
WordPress 필수 페이지 자동 생성 (AdSense 승인 필수)
- About (소개)
- Privacy Policy (개인정보처리방침)
- Contact (문의)
"""
import os, sys, base64, json

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
SITE_ID = os.environ.get("SITE_ID", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

if not all([WP_URL, WP_USER, WP_PASS]):
    print("ERROR: WP_URL, WP_USERNAME, WP_APP_PASSWORD 환경변수 필요")
    sys.exit(1)

import requests

# ── Supabase에서 기본정보 로드 (dashboard_config) ──
BLOG_OWNER = os.environ.get("BLOG_OWNER", "")
BLOG_DESC = os.environ.get("BLOG_DESC", "")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "")

if SUPABASE_URL and SUPABASE_KEY and SITE_ID:
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/dashboard_config?site_id=eq.{SITE_ID}&select=config",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        rows = resp.json()
        if rows and len(rows) > 0:
            cfg = rows[0].get("config", {})
            BLOG_OWNER = cfg.get("blog_owner", "") or BLOG_OWNER
            BLOG_DESC = cfg.get("blog_desc", "") or BLOG_DESC
            CONTACT_EMAIL = cfg.get("contact_email", "") or CONTACT_EMAIL
            print(f"  Supabase에서 기본정보 로드 완료 (site_id={SITE_ID})")
    except Exception as e:
        print(f"  Supabase 조회 실패: {e} — 환경변수 폴백 사용")

# 최종 폴백
if not BLOG_OWNER:
    BLOG_OWNER = "블로그 운영자"
if not BLOG_DESC:
    BLOG_DESC = "유용한 정보를 공유하는 블로그입니다"
if not CONTACT_EMAIL:
    CONTACT_EMAIL = "contact@example.com"

cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {cred}",
    "Content-Type": "application/json",
    "User-Agent": "AutoBlog/1.0",
}
API = f"{WP_URL}/wp-json/wp/v2"

domain = WP_URL.replace("https://", "").replace("http://", "").split("/")[0]


# ── Page Templates ──

def about_page():
    return {
        "title": "About",
        "slug": "about",
        "content": f"""
<h2>블로그 소개</h2>
<p>{BLOG_DESC}</p>
<p>이 블로그는 <strong>검증된 정보</strong>와 <strong>실용적인 팁</strong>을 제공하여
독자 여러분의 일상에 실질적인 도움을 드리고자 합니다.</p>

<h2>운영자 소개</h2>
<p>안녕하세요, <strong>{BLOG_OWNER}</strong>입니다.</p>
<p>다양한 분야의 전문 지식과 실제 경험을 바탕으로, 독자 여러분이 더 나은 선택을 할 수 있도록
정확하고 유용한 콘텐츠를 작성하고 있습니다.</p>

<h2>콘텐츠 원칙</h2>
<ul>
<li><strong>정확성</strong>: 모든 정보는 공식 출처와 데이터를 기반으로 합니다</li>
<li><strong>실용성</strong>: 바로 실행할 수 있는 구체적인 방법을 제시합니다</li>
<li><strong>투명성</strong>: 광고와 후원 콘텐츠는 명확히 표시합니다</li>
</ul>

<h2>문의</h2>
<p>콘텐츠에 대한 질문이나 제안은 <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>으로 보내주세요.</p>
""",
        "status": "publish",
    }


def privacy_page():
    return {
        "title": "Privacy Policy",
        "slug": "privacy-policy",
        "content": f"""
<h2>개인정보처리방침</h2>
<p><strong>{domain}</strong> (이하 "사이트")은 방문자의 개인정보를 중요하게 생각하며,
아래와 같이 개인정보를 처리하고 있습니다.</p>

<h3>1. 수집하는 개인정보</h3>
<p>본 사이트는 기본적으로 개인정보를 직접 수집하지 않습니다.
다만, 아래 서비스를 통해 자동으로 수집될 수 있습니다:</p>
<ul>
<li><strong>Google Analytics</strong>: 방문 통계 (IP 주소, 브라우저 정보, 페이지 조회)</li>
<li><strong>Google AdSense</strong>: 맞춤형 광고를 위한 쿠키</li>
<li><strong>댓글 시스템</strong>: 이름, 이메일 (선택적 입력)</li>
</ul>

<h3>2. 쿠키 사용</h3>
<p>본 사이트는 Google AdSense 및 Analytics 목적으로 쿠키를 사용합니다.
브라우저 설정에서 쿠키를 비활성화할 수 있으나, 일부 기능이 제한될 수 있습니다.</p>

<h3>3. 제3자 제공</h3>
<p>수집된 정보는 법적 요구가 있는 경우를 제외하고 제3자에게 제공하지 않습니다.</p>

<h3>4. 광고</h3>
<p>본 사이트는 Google AdSense를 통해 광고를 게재합니다.
Google은 사용자의 관심사에 기반한 광고를 표시하기 위해 쿠키를 사용할 수 있습니다.
자세한 내용은 <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener">Google 광고 정책</a>을 참조하세요.</p>

<h3>5. 제휴 링크</h3>
<p>일부 콘텐츠에는 제휴 마케팅 링크가 포함될 수 있으며,
이를 통한 구매 시 사이트 운영에 도움이 되는 소정의 수수료를 받을 수 있습니다.
제휴 링크가 포함된 콘텐츠는 별도로 표시합니다.</p>

<h3>6. 문의</h3>
<p>개인정보와 관련된 문의는 <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>으로 연락해주세요.</p>

<p><em>최종 업데이트: 2026년</em></p>
""",
        "status": "publish",
    }


def contact_page():
    return {
        "title": "Contact",
        "slug": "contact",
        "content": f"""
<h2>문의하기</h2>
<p>블로그 콘텐츠에 대한 질문, 제안, 협업 문의 등 무엇이든 환영합니다.</p>

<h3>이메일</h3>
<p><a href="mailto:{CONTACT_EMAIL}"><strong>{CONTACT_EMAIL}</strong></a></p>

<h3>문의 유형</h3>
<ul>
<li><strong>콘텐츠 문의</strong>: 글 내용에 대한 질문이나 정정 요청</li>
<li><strong>협업 제안</strong>: 광고, 협찬, 기고 등 비즈니스 문의</li>
<li><strong>기술 문의</strong>: 사이트 이용 관련 기술적 문제</li>
</ul>

<p>보내주신 메일은 영업일 기준 <strong>1~2일 이내</strong>에 답변드리겠습니다.</p>

<h3>운영 정보</h3>
<p>운영자: {BLOG_OWNER}<br/>
사이트: {domain}</p>
""",
        "status": "publish",
    }


# ── Create or Update Pages ──

PAGES = [about_page, privacy_page, contact_page]


def find_page_by_slug(slug):
    """slug로 기존 페이지 검색"""
    resp = requests.get(
        f"{API}/pages", params={"slug": slug, "status": "any"},
        headers=HEADERS, timeout=10
    )
    if resp.status_code == 200:
        pages = resp.json()
        if pages:
            return pages[0]
    return None


def create_or_update_page(page_data):
    """페이지 생성 또는 업데이트"""
    slug = page_data["slug"]
    existing = find_page_by_slug(slug)

    if existing:
        # Update existing
        resp = requests.post(
            f"{API}/pages/{existing['id']}",
            headers=HEADERS, json={
                "content": page_data["content"],
                "status": "publish",
            }, timeout=15
        )
        if resp.status_code == 200:
            print(f"  [UPDATE] {page_data['title']} (id={existing['id']})")
            return True
        else:
            print(f"  [ERR] {page_data['title']} update failed: {resp.status_code} {resp.text[:200]}")
            return False
    else:
        # Create new
        resp = requests.post(
            f"{API}/pages", headers=HEADERS, json=page_data, timeout=15
        )
        if resp.status_code == 201:
            print(f"  [NEW] {page_data['title']} (id={resp.json()['id']})")
            return True
        else:
            print(f"  [ERR] {page_data['title']} create failed: {resp.status_code} {resp.text[:200]}")
            return False


def main():
    print(f"=== 필수 페이지 생성 ({domain}) ===")
    print(f"  운영자: {BLOG_OWNER}")
    print(f"  이메일: {CONTACT_EMAIL}")
    print()

    success = 0
    for page_fn in PAGES:
        page_data = page_fn()
        if create_or_update_page(page_data):
            success += 1

    print(f"\n=== 완료: {success}/{len(PAGES)} 페이지 ===")
    if success < len(PAGES):
        sys.exit(1)


if __name__ == "__main__":
    main()
