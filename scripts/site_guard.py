"""발행 대상 사이트 가드 (중립 모듈 — main.py·etf_report.py가 함께 쓴다).

2026-09-13 결정: 이 저장소는 사용자 소유 두 사이트에만 글을 보낸다 (지인 사이트 자동화 종료).
사이트 ID만 검사하면 WP_URL을 다른 주소로 바꿔 우회할 수 있으므로, 실제로 글을 보낼 WP 주소의 호스트도
사이트별 도메인과 묶는다. 새 사이트는 코드 변경과 리뷰로만 추가한다(환경변수로 넓힐 수 없음).
"""
import os
from urllib.parse import urlsplit

# 사이트 ID → WordPress 도메인 (www. 없이, 소문자)
OWNED_SITES = {
    "site-1": "planx-ai.com",
    "site-1775046458524": "bomissu.com",
}
OWNED_SITE_IDS = frozenset(OWNED_SITES)


def wp_host(wp_url):
    """WP_URL에서 호스트만 뽑는다 (소문자, 앞의 'www.' 제거). 해석할 수 없으면 ''."""
    url = (wp_url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = "https://" + url
    try:
        host = (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def wp_url_allowed(site_id, wp_url):
    """site_id가 소유 사이트이고 wp_url 호스트가 그 사이트 도메인과 정확히 같을 때만 True.

    'planx-ai.com.example.net'·'planx-ai.com@example.net' 같은 우회 주소는 호스트가 달라 거부된다.
    """
    domain = OWNED_SITES.get(site_id)
    return bool(domain) and wp_host(wp_url) == domain


def editorial_review_required():
    """EDITORIAL_REVIEW_REQUIRED가 정확히 'false'일 때만 검토를 끈다. 미설정·오타는 검토 필수(fail-closed)."""
    return os.environ.get("EDITORIAL_REVIEW_REQUIRED", "true").strip().lower() != "false"
