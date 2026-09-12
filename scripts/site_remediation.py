#!/usr/bin/env python3
"""PlanX public-content cleanup. Plan first; authenticated apply keeps raw backups."""
import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SITE = 'https://planx-ai.com'


def clean_html(content):
    soup = BeautifulSoup(content, 'html.parser')
    changes = {'duplicate_images': 0, 'duplicate_tocs': 0}
    seen = set()
    for figure in list(soup.find_all('figure')):
        images = figure.find_all('img')
        if len(images) != 1:
            continue
        source = images[0].get('src')
        if not source:
            continue
        if source in seen:
            figure.decompose()
            changes['duplicate_images'] += 1
        else:
            seen.add(source)
    candidates = []
    for div in soup.find_all('div'):
        listing = div.find(['ol', 'ul'], recursive=False)
        if not listing or div.find(['h2', 'h3']):
            continue
        text = div.get_text(' ', strip=True)
        if len(text) < 1500 and re.search(r'이 글의 순서|^목차', text[:70]):
            candidates.append(div)
    if len(candidates) > 1:
        # Prefer the working anchor TOC over the AI-generated plain list.
        linked = [d for d in candidates if d.select('a[href^="#"]')]
        if linked:
            for div in candidates:
                if div is not linked[0]:
                    div.decompose()
                    changes['duplicate_tocs'] += 1
    return (str(soup) if any(changes.values()) else content), changes


def content_flags(content, title=''):
    soup = BeautifulSoup(content, 'html.parser')
    for node in soup.select('script,style,.author-box'):
        node.decompose()
    text = title + ' ' + soup.get_text(' ', strip=True)
    flags = []
    if re.search(r'직접.{0,12}(해보|써보|써봤|사용|경험)|제가.{0,25}(굴려|사용|해봤)|\d+주.{0,5}실사용|\d+년\s*(차|연구)', text):
        flags.append('experience_evidence_required')
    if re.search(r'실패율\s*\d|\d+%.{0,15}(복구|보장)|실패\s*없는|무조건|수익\s*보장', text):
        flags.append('unsupported_outcome_review')
    links = [a.get('href', '') for a in soup.find_all('a')]
    external = [u for u in links if urlparse(u).scheme in ('http','https') and
                urlparse(u).hostname not in ('planx-ai.com','www.planx-ai.com') and
                not any(x in urlparse(u).netloc for x in ('pexels.com','unsplash.com','pixabay.com','coupang.com'))]
    if not external:
        flags.append('no_external_reference_link')
    return flags


def build_plan(posts, pages=None):
    rows, groups = [], defaultdict(list)
    rewrites = json.loads((ROOT / 'content/adsense/replacements.json').read_text())
    for post in posts:
        content = post.get('content', {}).get('rendered', '')
        title = BeautifulSoup(post['title']['rendered'], 'html.parser').get_text()
        _, changes = clean_html(content)
        row = {'id': post['id'], 'slug': post['slug'], 'modified_gmt': post['modified_gmt'],
               'title': title, 'url': post['link'], 'changes': changes,
               'review_flags': content_flags(content, title)}
        if str(post['id']) in rewrites:
            row['replacement'] = rewrites[str(post['id'])]
        rows.append(row)
        # A shared slug is only a review candidate, not proof of duplicate content.
        groups[re.sub(r'-\d+$', '', post['slug'])].append(post['id'])
    page_rows = []
    for page in pages or []:
        if page['id'] not in (3, 6, 11):
            continue
        file = {3: 'privacy-advertising.html', 6: 'about.html', 11: 'contact.html'}[page['id']]
        path = ROOT / 'content/adsense' / file
        page_rows.append({'id':page['id'], 'kind':'pages', 'slug':page['slug'],
                          'modified_gmt':page['modified_gmt'], 'changes':{},
                          'replacement':{'path':str(path.relative_to(ROOT)),
                                         'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                                         'mode':'privacy_append' if page['id']==3 else 'replace'}})
    rows.extend(page_rows)
    return {'version': 1, 'site': SITE, 'post_count': len(posts), 'page_count':len(page_rows), 'rows': rows,
            'topic_families_for_review': {k: v for k,v in groups.items() if len(v)>1},
            'note': 'No automatic deletion, unpublishing, redirects, or AdSense pass score.'}


def write_private(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)


def raw_fields(post):
    return {key: (post[key]['raw'] if isinstance(post.get(key), dict) else post.get(key))
            for key in ('title', 'content', 'excerpt', 'status')}


def apply_plan(plan, session, backup_dir):
    if plan.get('site') != SITE or plan.get('version') != 1:
        raise ValueError('Unexpected target or plan version')
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for row in plan['rows']:
        if not any(row['changes'].values()) and not row.get('replacement'):
            continue
        kind = row.get('kind', 'posts')
        if kind not in ('posts', 'pages'):
            raise ValueError('Unexpected resource type')
        endpoint = f"{SITE}/wp-json/wp/v2/{kind}/{int(row['id'])}"
        backup = backup_dir / f"{kind}-{row['id']}.json"
        # Existing backup means a previous run may have written this post: do not overwrite it.
        if backup.exists():
            results.append({'id': row['id'], 'status': 'already_attempted_inspect_backup'})
            continue
        try:
            resp = session.get(endpoint, params={'context':'edit'}, timeout=30)
            resp.raise_for_status()
            post = resp.json()
            if post['slug'] != row['slug'] or post['modified_gmt'] != row['modified_gmt']:
                results.append({'id':row['id'], 'status':'changed_since_plan'})
                continue
            before = raw_fields(post)
            if not isinstance(before['content'], str):
                raise ValueError('Raw content unavailable')
            after, _ = clean_html(before['content'])
            payload = {'content': after}
            if row.get('replacement'):
                replacement = row['replacement']
                path = (ROOT / replacement['path']).resolve()
                content_root = (ROOT / 'content/adsense').resolve()
                if content_root not in path.parents:
                    raise ValueError('Invalid replacement path')
                data = path.read_bytes()
                if hashlib.sha256(data).hexdigest() != replacement['sha256']:
                    raise ValueError('Replacement changed after review')
                replacement_content = data.decode()
                if replacement.get('mode') == 'privacy_append':
                    # Keep the existing policy; correct the published placeholder and append Google's notice.
                    base_content = before['content'].replace('contact@example.com', 'planxsol@gmail.com')
                    replacement_content = base_content if 'Google 광고 쿠키 및 맞춤 광고 선택' in base_content else base_content + '\n' + replacement_content
                payload = {'content':replacement_content}
                for field in ('title','excerpt'):
                    if field in replacement:
                        payload[field] = replacement[field]
            if all(before.get(k) == v for k,v in payload.items()):
                results.append({'id':row['id'], 'status':'unchanged'})
                continue
            write_private(backup, {'site':SITE,'kind':kind,'id':row['id'],'before':before,'applied_fields':payload})
            # Never follow a redirect carrying credentials to another host.
            resp = session.post(endpoint, json=payload, timeout=30, allow_redirects=False)
            if resp.status_code not in (200,201):
                raise ValueError('Write rejected')
            resp = session.get(endpoint, params={'context':'edit'}, timeout=30)
            resp.raise_for_status()
            actual = raw_fields(resp.json())
            if any(actual.get(k) != v for k,v in payload.items()) or actual['status'] != before['status']:
                raise ValueError('Write verification mismatch; inspect backup')
            results.append({'id':row['id'], 'status':'verified'})
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError):
            results.append({'id':row['id'], 'status':'failed_inspect_backup'})
            # Fail fast so an upstream/permission failure does not affect the entire site.
            break
    return results


def restore_backup(path, session):
    saved = json.loads(Path(path).read_text())
    if saved.get('site') != SITE:
        raise ValueError('Unexpected backup target')
    kind = saved.get('kind', 'posts')
    if kind not in ('posts','pages'):
        raise ValueError('Unexpected backup kind')
    endpoint = f"{SITE}/wp-json/wp/v2/{kind}/{int(saved['id'])}"
    response = session.get(endpoint, params={'context':'edit'}, timeout=30)
    response.raise_for_status()
    current = raw_fields(response.json())
    if any(current.get(k) != v for k,v in saved['applied_fields'].items()):
        raise ValueError('Post changed after apply: automatic restore stopped')
    response = session.post(endpoint, json=saved['before'], timeout=30, allow_redirects=False)
    if response.status_code != 200:
        raise ValueError('Restore failed')
    response = session.get(endpoint, params={'context':'edit'}, timeout=30)
    response.raise_for_status()
    if raw_fields(response.json()) != saved['before']:
        raise ValueError('Restore verification failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--plan-from', help='public posts.json snapshot')
    group.add_argument('--apply', help='reviewed plan JSON')
    group.add_argument('--restore', help='one raw backup JSON')
    parser.add_argument('--pages-from', help='public pages.json snapshot')
    parser.add_argument('--output', default='remediation-plan.json')
    parser.add_argument('--backup-dir', default='.private-backups/adsense')
    args = parser.parse_args()
    if args.plan_from:
        plan = build_plan(json.loads(Path(args.plan_from).read_text()), json.loads(Path(args.pages_from).read_text()) if args.pages_from else None)
        Path(args.output).write_text(json.dumps(plan,ensure_ascii=False,indent=2))
        print(f"Planned {plan['post_count']} posts. No site writes.")
        return 0
    if os.environ.get('WP_URL', '').rstrip('/') != SITE or not all(os.environ.get(k) for k in ('WP_USERNAME','WP_APP_PASSWORD')):
        parser.error('Set target WP_URL and WordPress application credentials in environment; never paste them in logs.')
    with requests.Session() as session:
        session.auth = (os.environ['WP_USERNAME'], os.environ['WP_APP_PASSWORD'])
        if args.restore:
            restore_backup(args.restore, session)
            print('Restore verified.')
            return 0
        result = apply_plan(json.loads(Path(args.apply).read_text()), session, args.backup_dir)
        Path(args.output).write_text(json.dumps(result,indent=2))
        print(json.dumps({s:sum(r['status']==s for r in result) for s in sorted({r['status'] for r in result})}))
        return int(any(r['status'] not in ('verified','unchanged') for r in result))


if __name__ == '__main__':
    raise SystemExit(main())
