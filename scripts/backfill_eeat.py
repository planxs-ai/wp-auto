#!/usr/bin/env python3
"""
기존 발행 글에 E-E-A-T 블록(저자 박스 + 면책조항)을 백필(소급 삽입).

신규 글은 main.py의 _inject_eeat_blocks()가 발행 시 자동 삽입하지만,
그 기능 배포 이전에 발행된 글들은 저자 박스/면책이 없다.
애드센스 리뷰어는 기존 글도 확인하므로, 누락된 글에 소급 삽입한다.

- 멱등: 이미 author-box가 있으면 건너뜀
- disclaimer의 '최종 업데이트'는 각 글의 modified 날짜를 사용(날짜 위조 안 함)
- Article JSON-LD는 별도 경로에서 처리되므로 여기서는 다루지 않음

사용:
  WP_URL=... WP_USERNAME=... WP_APP_PASSWORD=... python scripts/backfill_eeat.py [--dry-run] [--limit N]
"""
import os, sys, base64, time, argparse
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    print("requests 필요: pip install requests"); sys.exit(1)

WP_URL = os.environ.get("WP_URL", "").rstrip("/")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
if not all([WP_URL, WP_USER, WP_PASS]):
    print("ERROR: WP_URL, WP_USERNAME, WP_APP_PASSWORD 환경변수 필요"); sys.exit(1)

API = f"{WP_URL}/wp-json/wp/v2"
cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
HEADERS = {"Authorization": f"Basic {cred}", "Content-Type": "application/json", "User-Agent": "AutoBlog-Backfill/1.0"}

# ── 사이트별 저자 (main.py SITE_AUTHORS와 동일) ──
SITE_AUTHORS = {
    "bomissu.com": {"name": "Bomissu 운영자", "bio": "재테크·부업·정부지원금 15년 연구 · 정보성 분석 전문", "publisher": "Bomissu"},
    "planx-ai.com": {"name": "PlanX 투자리서치팀", "bio": "퀀트 전략·ETF 모멘텀·섹터 로테이션 분석 전문", "publisher": "PlanX AI"},
}
DEFAULT_AUTHOR = {"name": "편집팀", "bio": "정보성 분석 전문", "publisher": ""}


def _initial_avatar(name):
    """이름 첫 글자 Gold 그라데이션 SVG 아바타 → base64 data URI (항상 렌더링 보장)."""
    initial = (name or "B").strip()[:1].upper()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="#D4AF37"/><stop offset="1" stop-color="#8B6914"/></linearGradient></defs>'
        f'<rect width="64" height="64" rx="32" fill="url(#g)"/>'
        f'<text x="32" y="42" font-family="Georgia,serif" font-size="30" font-weight="700" '
        f'fill="#fff" text-anchor="middle">{initial}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _resolve_author():
    host = urlparse(WP_URL).netloc.replace("www.", "")
    return SITE_AUTHORS.get(host, DEFAULT_AUTHOR)


def _author_box_html(author):
    avatar = _initial_avatar(author["name"])
    return (
        "\n<div class=\"author-box\" style=\"background:#FEFCF8;border:1px solid rgba(26,22,18,0.08);"
        "border-radius:12px;padding:20px 24px;margin:32px 0;display:flex;gap:16px;align-items:center\">"
        f"<img src=\"{avatar}\" alt=\"{author['name']}\" style=\"width:64px;height:64px;border-radius:50%;flex-shrink:0\"/>"
        "<div>"
        f"<div style=\"font-family:Georgia,serif;font-size:17px;font-weight:700;color:#1A1612\">{author['name']}</div>"
        f"<div style=\"font-size:13px;color:#6B5E52;margin-top:4px\">{author['bio']}</div>"
        "<div style=\"font-size:12px;color:#9E8E7E;margin-top:6px\">모든 수치는 공식 출처를 기반으로 재검증합니다.</div>"
        "</div></div>\n"
    )


def _disclaimer_html(updated_kr):
    return (
        "\n<div class=\"disclaimer\" style=\"background:#FFFBEB;border:1px solid #FDE68A;"
        "padding:12px 16px;margin:24px 0;border-radius:6px;font-size:13px;color:#6B5E52\">"
        "<strong>⚠️ 고지사항</strong>: 본 글은 일반 정보 제공 목적이며, 개별 투자·법률·세무 판단을 대체하지 않습니다. "
        f"구체적 결정은 전문가 상담 후 진행하세요. 최종 업데이트: {updated_kr}</div>\n"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="처리할 최대 글 수 (0=전체)")
    args = ap.parse_args()

    author = _resolve_author()
    host = urlparse(WP_URL).netloc
    print(f"=== E-E-A-T 백필: {host} | 저자: {author['name']} | {'DRY-RUN' if args.dry_run else 'LIVE'} ===")

    page, processed, updated, skipped, errors = 1, 0, 0, 0, 0
    while True:
        r = requests.get(f"{API}/posts", headers=HEADERS,
                         params={"per_page": 100, "page": page, "status": "publish",
                                 "_fields": "id,modified,content,title"}, timeout=30)
        if r.status_code != 200:
            if r.status_code == 400:  # 페이지 초과 → 끝
                break
            print(f"  조회 실패 page={page}: {r.status_code}"); break
        posts = r.json()
        if not posts:
            break

        for p in posts:
            processed += 1
            pid = p["id"]
            content = (p.get("content") or {}).get("raw") or (p.get("content") or {}).get("rendered") or ""
            title = (p.get("title") or {}).get("rendered", "")[:40]

            if 'class="author-box"' in content:
                skipped += 1
                continue

            modified = (p.get("modified") or "")[:10]
            try:
                y, m, d = modified.split("-")
                updated_kr = f"{y}년 {m}월 {d}일"
            except Exception:
                updated_kr = modified or ""

            new_content = content.rstrip()
            if 'class="disclaimer"' not in new_content:
                new_content += _disclaimer_html(updated_kr)
            new_content += _author_box_html(author)

            if args.dry_run:
                print(f"  [DRY] {pid} {title} → 추가 예정")
                updated += 1
            else:
                ok = False
                for attempt in range(3):
                    try:
                        up = requests.post(f"{API}/posts/{pid}", headers=HEADERS,
                                           json={"content": new_content}, timeout=60)
                        if up.status_code == 200:
                            print(f"  [OK] {pid} {title}")
                            updated += 1; ok = True
                        else:
                            print(f"  [ERR] {pid} {title}: {up.status_code} {up.text[:120]}")
                        break  # 응답을 받았으면(성공/HTTP오류) 재시도 안 함
                    except requests.exceptions.RequestException as e:
                        print(f"  [RETRY {attempt+1}/3] {pid} {title}: {type(e).__name__}")
                        time.sleep(3)
                if not ok:
                    errors += 1
                time.sleep(0.3)

            if args.limit and updated >= args.limit:
                print(f"\n--limit {args.limit} 도달 — 중단")
                _summary(processed, updated, skipped, errors); return
        page += 1

    _summary(processed, updated, skipped, errors)


def _summary(processed, updated, skipped, errors):
    print(f"\n=== 완료 ===")
    print(f"  처리: {processed} | 삽입: {updated} | 이미있음(스킵): {skipped} | 오류: {errors}")


if __name__ == "__main__":
    main()
