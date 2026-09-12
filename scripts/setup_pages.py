#!/usr/bin/env python3
"""Create missing information drafts; never overwrite existing pages."""
import base64
import os
from urllib.parse import urlparse
import requests
try:
    from .editorial_pages import build_pages, create_missing_drafts
except ImportError:
    from editorial_pages import build_pages, create_missing_drafts


def main():
    url = os.environ.get('WP_URL', '').rstrip('/')
    user = os.environ.get('WP_USERNAME', '')
    password = os.environ.get('WP_APP_PASSWORD', '')
    parsed = urlparse(url)
    if not user or not password or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        print('HTTPS WP_URL 및 WordPress 환경변수를 확인하세요. 값은 출력하지 않습니다.')
        return 1
    owner = os.environ.get('BLOG_OWNER', '')
    description = os.environ.get('BLOG_DESC', '')
    email = os.environ.get('CONTACT_EMAIL', '')
    sb_url, sb_key, site_id = (os.environ.get(k, '') for k in ('SUPABASE_URL', 'SUPABASE_KEY', 'SITE_ID'))
    if sb_url and sb_key and site_id:
        try:
            response = requests.get(f"{sb_url.rstrip('/')}/rest/v1/dashboard_config",
                                    headers={'apikey': sb_key, 'Authorization': f'Bearer {sb_key}'},
                                    params={'site_id': f'eq.{site_id}', 'select': 'config'}, timeout=15)
            response.raise_for_status()
            rows = response.json()
            cfg = rows[0].get('config', {}) if isinstance(rows, list) and rows else {}
            owner = owner or cfg.get('blog_owner', '')
            description = description or cfg.get('blog_desc', '')
            email = email or cfg.get('contact_email', '')
        except (requests.RequestException, ValueError, TypeError, AttributeError):
            print('사이트 정보 조회 실패. 페이지를 변경하지 않았습니다.')
            return 1
    try:
        pages = build_pages(parsed.hostname, owner, description, email)
    except ValueError as error:
        print(str(error))
        return 1
    cred = base64.b64encode(f'{user}:{password}'.encode()).decode()
    created, skipped, failed = create_missing_drafts(
        url, {'Authorization': f'Basic {cred}', 'Content-Type': 'application/json'}, pages, requests)
    print(f'초안 {len(created)} / 기존 유지 {len(skipped)} / 실패 {len(failed)}')
    print('WordPress에서 실제 운영정보와 개인정보 처리 현황을 확인한 뒤 공개하세요.')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
