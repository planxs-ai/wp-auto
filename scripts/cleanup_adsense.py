"""
애드센스 승인을 위한 사이트 정리 스크립트
- Uncategorized 글 → 적절한 카테고리로 재분류
- 블로그 자동화 / 쿠팡 핫딜 글 → 비공개 처리
- 소개(About) 페이지 생성
- HTML 깨진 글 수정

사용법:
  WP_URL=https://sinjum-ai.com WP_USERNAME=admin WP_APP_PASSWORD="xxxx" python scripts/cleanup_adsense.py
"""
import os
import re
import sys
import json
import base64
import requests

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")

if not WP_URL or not WP_USER or not WP_PASS:
    print("ERROR: WP_URL, WP_USERNAME, WP_APP_PASSWORD 환경변수 필요")
    sys.exit(1)

API = f"{WP_URL}/wp-json/wp/v2"
cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {
    "Authorization": f"Basic {cred}",
    "Content-Type": "application/json",
}

# ─── 카테고리 키워드 매핑 ───
CATEGORY_KEYWORDS = {
    "재테크 입문": ["저축", "재테크", "자산 관리", "돈 모으", "통장", "파킹통장", "비상금", "금융", "재무"],
    "적금·예금": ["적금", "예금", "금리", "이자", "CMA", "예적금"],
    "절세·세금": ["세금", "절세", "연말정산", "종합소득세", "부가세", "세액공제", "소득공제"],
    "부동산": ["부동산", "전세", "월세", "아파트", "집값", "청약", "임대", "매매"],
    "주식·배당": ["주식", "배당", "증권", "코스피", "나스닥", "투자", "S&P"],
    "ETF·인덱스": ["ETF", "인덱스", "펀드", "TDF"],
    "AI 투자": ["AI 투자", "로보어드바이저", "빅데이터 투자", "알고리즘", "퀀트"],
    "연금·노후": ["연금", "노후", "은퇴", "IRP", "퇴직금", "국민연금"],
    "생활정보": ["생활", "꿀팁", "정보", "가계부", "신용점수", "카드"],
    "IT/전자": ["IT", "전자", "스마트", "앱", "테크"],
    "건강": ["건강", "운동", "다이어트", "영양"],
}

# 비공개 대상 카테고리
DRAFT_CATEGORIES = ["블로그 자동화", "쿠팡 핫딜", "쿠팡 뷰티/미용", "쿠팡 생활/주방"]

# 카테고리 통합 매핑 (기존 분산 카테고리 → 핵심 5개로)
CATEGORY_MERGE = {
    "재테크 입문": "재테크 기초",
    "적금·예금": "재테크 기초",
    "AI 투자": "주식·투자",
    "주식·배당": "주식·투자",
    "ETF·인덱스": "주식·투자",
    "절세·세금": "절세·세금",
    "부동산": "부동산·연금",
    "연금·노후": "부동산·연금",
    "생활정보": "생활 꿀팁",
    "IT/전자": "생활 꿀팁",
    "건강": "생활 꿀팁",
}


def get_all_categories():
    """모든 카테고리 조회"""
    cats = {}
    page = 1
    while True:
        resp = requests.get(f"{API}/categories?per_page=100&page={page}", headers=HEADERS, timeout=15)
        data = resp.json()
        if not data:
            break
        for c in data:
            cats[c["name"]] = c["id"]
        if len(data) < 100:
            break
        page += 1
    return cats


def get_or_create_category(name, cats):
    """카테고리 ID 반환, 없으면 생성"""
    if name in cats:
        return cats[name]
    resp = requests.post(f"{API}/categories", headers=HEADERS, json={"name": name}, timeout=15)
    if resp.status_code in (200, 201):
        cat_id = resp.json()["id"]
        cats[name] = cat_id
        print(f"  카테고리 생성: {name} (ID: {cat_id})")
        return cat_id
    return None


def classify_post(title):
    """제목 기반으로 카테고리 추론"""
    title_lower = title.lower()
    for cat_name, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_lower:
                return cat_name
    return "생활정보"  # 기본 폴백


def get_posts_by_category(cat_id, per_page=100):
    """특정 카테고리 글 조회"""
    posts = []
    page = 1
    while True:
        resp = requests.get(
            f"{API}/posts?categories={cat_id}&per_page={per_page}&page={page}&_fields=id,title,status,content",
            headers=HEADERS, timeout=30
        )
        if resp.status_code != 200:
            break
        data = resp.json()
        if not data:
            break
        posts.extend(data)
        if len(data) < per_page:
            break
        page += 1
    return posts


def clean_html_document_tags(content):
    """HTML 문서 태그 제거"""
    content = re.sub(r'<!DOCTYPE\s+html[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'</?html[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<head[^>]*>.*?</head>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'</?body[^>]*>', '', content, flags=re.IGNORECASE)
    content = re.sub(r'<meta[^>]*/?>', '', content, flags=re.IGNORECASE)
    return content


def clean_inline_css(content):
    """본문 내 인라인 <style> 블록 제거 (AdSense 품질 신호 개선)"""
    # AutoBlog이 주입한 <style> 블록
    content = re.sub(
        r'\s*<style>\s*/\*\s*AutoBlog\s.*?\*/.*?</style>\s*',
        '', content, flags=re.DOTALL | re.IGNORECASE
    )
    # 본문 상단 일반 <style> 블록
    if content.lstrip().startswith('<style'):
        content = re.sub(
            r'^\s*<style[^>]*>.*?</style>\s*',
            '', content, count=1, flags=re.DOTALL | re.IGNORECASE
        )
    return content.lstrip('\n')


def create_contact_page(site_name="신줌AI"):
    """연락처 페이지 생성"""
    resp = requests.get(f"{API}/pages?slug=contact&_fields=id", headers=HEADERS, timeout=10)
    if resp.json():
        print("연락처(Contact) 페이지 이미 존재 — 스킵")
        return

    contact_content = f"""
<h2>문의하기</h2>
<p>{site_name}에 대한 문의, 제안, 또는 수정 요청이 있으시면 아래 이메일로 연락해주세요.</p>

<h3>이메일</h3>
<p>📧 <strong>planxsol@gmail.com</strong></p>

<h3>응답 안내</h3>
<p>문의하신 내용은 영업일 기준 1~2일 이내에 답변드립니다.
광고, 협찬, 콘텐츠 제휴 관련 문의도 환영합니다.</p>

<h3>콘텐츠 수정 요청</h3>
<p>게시된 글에 사실과 다른 정보가 있거나 수정이 필요한 경우,
해당 글 URL과 함께 수정 요청 내용을 보내주시면 빠르게 반영하겠습니다.</p>
"""
    resp = requests.post(f"{API}/pages", headers=HEADERS, json={
        "title": "문의하기",
        "content": contact_content,
        "status": "publish",
        "slug": "contact",
    }, timeout=15)

    if resp.status_code in (200, 201):
        print(f"연락처(Contact) 페이지 생성 완료: {WP_URL}/contact/")
    else:
        print(f"연락처 페이지 생성 실패: {resp.status_code}")


def create_privacy_page(site_name="신줌AI"):
    """개인정보처리방침 페이지 생성"""
    resp = requests.get(f"{API}/pages?slug=privacy-policy&_fields=id", headers=HEADERS, timeout=10)
    if resp.json():
        print("개인정보처리방침 페이지 이미 존재 — 스킵")
        return

    privacy_content = f"""
<h2>개인정보처리방침</h2>
<p><strong>{site_name}</strong>(이하 "사이트")는 이용자의 개인정보를 중요시하며,
「개인정보 보호법」을 준수하고 있습니다.</p>

<h3>1. 수집하는 개인정보 항목</h3>
<p>사이트는 서비스 제공을 위해 최소한의 개인정보를 수집합니다.</p>
<p>자동 수집 항목: 접속 IP, 쿠키, 방문 일시, 서비스 이용 기록</p>

<h3>2. 개인정보의 수집 및 이용 목적</h3>
<p>수집된 정보는 콘텐츠 제공, 서비스 개선, 통계 분석 목적으로만 활용됩니다.</p>

<h3>3. 개인정보의 보유 및 이용 기간</h3>
<p>이용 목적이 달성된 후에는 해당 정보를 지체 없이 파기합니다.</p>

<h3>4. 광고 및 제3자 서비스</h3>
<p>사이트는 Google AdSense, 쿠팡 파트너스 등 제3자 광고 서비스를 이용할 수 있으며,
이들 서비스는 자체적인 개인정보처리방침에 따라 쿠키를 사용할 수 있습니다.</p>
<p>Google의 개인정보처리방침: <a href="https://policies.google.com/privacy" target="_blank">https://policies.google.com/privacy</a></p>

<h3>5. 개인정보 보호책임자</h3>
<p>이메일: planxsol@gmail.com</p>

<h3>6. 방침 변경 안내</h3>
<p>본 방침은 시행일로부터 적용되며, 변경 시 사이트를 통해 공지합니다.</p>
<p><em>시행일: 2026년 4월 5일</em></p>
"""
    resp = requests.post(f"{API}/pages", headers=HEADERS, json={
        "title": "개인정보처리방침",
        "content": privacy_content,
        "status": "publish",
        "slug": "privacy-policy",
    }, timeout=15)

    if resp.status_code in (200, 201):
        print(f"개인정보처리방침 페이지 생성 완료: {WP_URL}/privacy-policy/")
    else:
        print(f"개인정보처리방침 페이지 생성 실패: {resp.status_code}")


def merge_categories(cats):
    """분산된 카테고리를 핵심 5개로 통합"""
    print("\n[5/6] 카테고리 통합 (11개 → 5개)")
    merged_count = 0

    for old_name, new_name in CATEGORY_MERGE.items():
        if old_name not in cats or old_name == new_name:
            continue

        old_id = cats[old_name]
        new_id = get_or_create_category(new_name, cats)
        if not new_id:
            continue

        # 이전 카테고리의 글들을 새 카테고리로 이동
        posts = get_posts_by_category(old_id)
        for p in posts:
            current_cats = [c for c in (p.get("categories") or []) if c != old_id]
            current_cats.append(new_id)
            if update_post(p["id"], {"categories": list(set(current_cats))}):
                merged_count += 1

        print(f"  {old_name} → {new_name}: {len(posts)}편 이동")

    print(f"  → {merged_count}편 카테고리 통합 완료")


def update_post(post_id, data):
    """글 업데이트"""
    resp = requests.post(f"{API}/posts/{post_id}", headers=HEADERS, json=data, timeout=15)
    return resp.status_code in (200, 201)


def create_about_page(site_name="신줌AI"):
    """소개 페이지 생성"""
    # 기존 About 페이지 확인
    resp = requests.get(f"{API}/pages?slug=about&_fields=id", headers=HEADERS, timeout=10)
    if resp.json():
        print("소개(About) 페이지 이미 존재 — 스킵")
        return

    about_content = f"""
<h2>안녕하세요, {site_name}입니다</h2>
<p>{site_name}는 재테크, 투자, 절세 등 금융 정보를 알기 쉽게 전달하는 블로그입니다.
복잡한 금융 용어를 일상 언어로 풀어내고, 실생활에 바로 적용할 수 있는 정보를 제공합니다.</p>

<h2>어떤 정보를 다루나요?</h2>
<ul>
<li><strong>재테크 입문</strong> — 저축, 통장 관리, 자산 설계의 기초</li>
<li><strong>적금·예금</strong> — 금리 비교, 최적의 예적금 전략</li>
<li><strong>절세·세금</strong> — 연말정산, 종합소득세, 세액공제 가이드</li>
<li><strong>부동산</strong> — 전세/매매 체크리스트, 청약 정보</li>
<li><strong>주식·ETF</strong> — 배당주, 인덱스 펀드, 장기 투자 전략</li>
<li><strong>연금·노후</strong> — 국민연금, IRP, 퇴직금 관리</li>
</ul>

<h2>운영 원칙</h2>
<p>모든 글은 공신력 있는 데이터와 공식 자료를 기반으로 작성합니다.
검증되지 않은 수익률이나 과장된 투자 정보는 다루지 않습니다.</p>

<h2>문의</h2>
<p>궁금한 점이나 제안이 있으시면 <a href="/contact/">연락처 페이지</a>를 통해 문의해주세요.</p>
"""
    resp = requests.post(f"{API}/pages", headers=HEADERS, json={
        "title": f"{site_name} 소개",
        "content": about_content,
        "status": "publish",
        "slug": "about",
    }, timeout=15)

    if resp.status_code in (200, 201):
        print(f"소개(About) 페이지 생성 완료: {WP_URL}/about/")
    else:
        print(f"소개 페이지 생성 실패: {resp.status_code} {resp.text[:200]}")


def main():
    print("=" * 60)
    print("애드센스 사이트 정리 스크립트")
    print(f"대상: {WP_URL}")
    print("=" * 60)

    cats = get_all_categories()
    print(f"\n카테고리 {len(cats)}개 로드 완료")

    # ─── 1. 블로그 자동화 / 쿠팡 글 비공개 처리 ───
    print("\n[1/4] 비공개 처리: 블로그 자동화 + 쿠팡 카테고리")
    draft_count = 0
    for cat_name in DRAFT_CATEGORIES:
        if cat_name not in cats:
            continue
        cat_id = cats[cat_name]
        posts = get_posts_by_category(cat_id)
        for p in posts:
            if p["status"] == "publish":
                if update_post(p["id"], {"status": "draft"}):
                    draft_count += 1
                    print(f"  비공개: [{p['id']}] {p['title']['rendered'][:40]}")
    print(f"  → {draft_count}편 비공개 처리 완료")

    # ─── 2. Uncategorized 글 재분류 ───
    print("\n[2/4] Uncategorized 글 재분류")
    uncat_id = cats.get("Uncategorized") or cats.get("미분류")
    if not uncat_id:
        print("  Uncategorized 카테고리를 찾을 수 없습니다")
    else:
        uncat_posts = get_posts_by_category(uncat_id)
        reclassified = 0
        for p in uncat_posts:
            title = p["title"]["rendered"]
            new_cat_name = classify_post(title)
            new_cat_id = get_or_create_category(new_cat_name, cats)
            if new_cat_id and new_cat_id != uncat_id:
                if update_post(p["id"], {"categories": [new_cat_id]}):
                    reclassified += 1
                    print(f"  재분류: [{p['id']}] {title[:35]} → {new_cat_name}")
        print(f"  → {reclassified}편 재분류 완료")

    # ─── 3. HTML 깨진 글 수정 + 인라인 CSS 제거 ───
    print("\n[3/6] HTML 문서 태그 + 인라인 CSS 정리")
    fixed_count = 0
    css_count = 0
    page = 1
    while True:
        resp = requests.get(
            f"{API}/posts?per_page=50&page={page}&_fields=id,title,content",
            headers=HEADERS, timeout=30
        )
        if resp.status_code != 200:
            break
        posts = resp.json()
        if not posts:
            break
        for p in posts:
            content = p["content"]["rendered"]
            needs_fix = False

            # 원본 content 가져오기
            raw_resp = requests.get(
                f"{API}/posts/{p['id']}?context=edit&_fields=content",
                headers=HEADERS, timeout=15
            )
            if raw_resp.status_code != 200:
                continue

            raw_content = raw_resp.json()["content"]["raw"]
            cleaned = raw_content

            # HTML 문서 태그 제거
            if "<!DOCTYPE" in content or "<html" in content or "<body" in content:
                cleaned = clean_html_document_tags(cleaned)
                needs_fix = True

            # 인라인 CSS 제거
            if "<style" in cleaned[:500]:
                cleaned = clean_inline_css(cleaned)
                needs_fix = True
                css_count += 1

            if needs_fix and cleaned != raw_content:
                if update_post(p["id"], {"content": cleaned}):
                    fixed_count += 1
                    print(f"  수정: [{p['id']}] {p['title']['rendered'][:40]}")

        if len(posts) < 50:
            break
        page += 1
    print(f"  → {fixed_count}편 수정 완료 (HTML {fixed_count - css_count}, CSS {css_count})")

    # ─── 4. 소개(About) 페이지 생성 ───
    print("\n[4/6] 소개(About) 페이지 확인/생성")
    create_about_page()

    # ─── 5. 연락처 + 개인정보처리방침 페이지 ───
    print("\n[5/6] 연락처 + 개인정보처리방침 페이지")
    create_contact_page()
    create_privacy_page()

    # ─── 6. 카테고리 통합 ───
    merge_categories(cats)

    # ─── 결과 요약 ───
    print("\n" + "=" * 60)
    print("정리 완료!")
    print(f"  비공개 처리: {draft_count}편")
    print(f"  카테고리 재분류: {reclassified if uncat_id else 0}편")
    print(f"  HTML/CSS 수정: {fixed_count}편")
    print(f"  필수 페이지: About + Contact + Privacy Policy 확인")
    print(f"  카테고리 통합: 11개 → 5개")
    print("=" * 60)
    print("\n다음 단계: 애드센스 재심사 요청")


if __name__ == "__main__":
    main()
