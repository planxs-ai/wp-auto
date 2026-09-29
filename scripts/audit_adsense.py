#!/usr/bin/env python3
"""Bounded, public GET-only review inventory. No credentials, mutation, or approval score."""
import argparse
import json
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
import requests


class Links(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.hrefs = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.hrefs.extend(v for k, v in attrs if k == "href" and v)


def review_flags(content):
    text = unescape(re.sub(r"<[^>]+>", " ", content))
    flags = []
    if re.search(r"직접.{0,12}(해보|써보|써봤|경험|사용)|제가.{0,20}(실제로|투자|사용)|\d+년\s*(차|연구)", text):
        flags.append("체험·경력 주장: 실제 기록 대조 필요")
    if re.search(r"수익.{0,8}보장|100%.{0,8}수익|실패\s*없는|무조건\s*최저", text):
        flags.append("보장·단정 표현 검토")
    if "example.com" in text or "[확인 필요]" in text:
        flags.append("미완성 운영정보")
    external = [u for u in Links(content).hrefs if urlparse(u).scheme in {"http", "https"}]
    if not external:
        flags.append("외부 근거 링크 없음: 원문 확인 경로 검토")
    if len(text.strip()) < 500:
        flags.append("짧은 본문: 독자에게 충분한 설명인지 검토 (내부 기준)")
    return flags


def audit(url, max_pages=1):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("자격증명·쿼리 없는 HTTPS 사이트 주소를 사용하세요.")
    base = url.rstrip("/")
    result = {"site": base, "scope": "public GET only; flags require human review",
              "errors": [], "posts": [], "pages": [], "sample_complete": False}
    # No website credentials: disable implicit .netrc authentication.
    with requests.Session() as session:
        session.auth = lambda request: request  # Suppress .netrc auth; retain required proxy routing.
        def get(path, params=None):
            response = session.get(base + path, params=params, timeout=15)
            response.raise_for_status()
            return response
        try:
            home = get("/")
            result["home_status"] = home.status_code
            result["home_link_count"] = len(Links(home.text).hrefs)
            result["home_noindex_hint"] = bool(re.search(r'<meta[^>]+content=["\'][^"\']*noindex', home.text, re.I))
        except requests.RequestException:
            result["errors"].append("홈 조회 실패")
        try:
            for page in range(1, max_pages + 1):
                response = get("/wp-json/wp/v2/posts", {"per_page": 20, "page": page,
                               "_fields": "id,link,title,content", "orderby": "date", "order": "desc"})
                posts = response.json()
                if not isinstance(posts, list):
                    raise ValueError("Invalid posts")
                for post in posts:
                    result["posts"].append({"id": post["id"], "url": post.get("link", ""),
                                            "flags": review_flags(post.get("content", {}).get("rendered", ""))})
                total = int(response.headers.get("X-WP-TotalPages", "0"))
                if total and page >= total or len(posts) < 20:
                    result["sample_complete"] = True
                    break
        except (requests.RequestException, ValueError, KeyError, TypeError):
            result["errors"].append("공개 글 목록 조회 실패 또는 일부만 조회됨")
        for slug in ("about", "about-us", "contact", "privacy-policy", "editorial-policy"):
            try:
                pages = get("/wp-json/wp/v2/pages", {"slug": slug, "_fields": "id,link,content"}).json()
                if not isinstance(pages, list):
                    raise ValueError("Invalid pages")
                result["pages"].append({"slug": slug, "public": bool(pages),
                                        "urls": [p.get("link", "") for p in pages]})
            except (requests.RequestException, ValueError, TypeError):
                result["errors"].append(f"페이지 조회 실패: {slug}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--max-pages", type=int, choices=range(1, 6), default=1)
    args = parser.parse_args()
    try:
        result = audit(args.url, args.max_pages)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
