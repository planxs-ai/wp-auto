#!/usr/bin/env python3
"""발행 전 HTML 정리 — 사이트에 묶이지 않은 중립 모듈.

main.py 파이프라인이 모든 사이트에 공통으로 쓴다. 네트워크 접근이 없고 사이트 상수도 없다.
PR #3(site_remediation.clean_html)에서 옮겨 왔다. planx 전용 정비 도구와 분리하기 위해서다.

하는 일 두 가지:
- 같은 이미지(src)가 <figure>로 두 번 이상 들어가면 첫 번째만 남긴다.
- '이 글의 순서'/'목차' 목록이 둘 이상이면 앵커 링크가 있는 목차 하나만 남긴다.

바꿀 것이 없으면 입력 문자열을 그대로 돌려준다(재직렬화하지 않음).
BeautifulSoup이 설치돼 있지 않으면 아무것도 바꾸지 않는다.
"""
import re

try:
    from bs4 import BeautifulSoup
except ImportError:  # 의존성이 없으면 원문을 그대로 쓴다
    BeautifulSoup = None

_TOC_HEAD = re.compile(r'이 글의 순서|^목차')


def clean_html(content):
    """(정리된 HTML, 변경 건수 dict)를 돌려준다. 변경이 없으면 원문 그대로."""
    changes = {'duplicate_images': 0, 'duplicate_tocs': 0}
    if not content or BeautifulSoup is None:
        return content, changes

    soup = BeautifulSoup(content, 'html.parser')

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
        if len(text) < 1500 and _TOC_HEAD.search(text[:70]):
            candidates.append(div)
    if len(candidates) > 1:
        # AI가 만든 평문 목록보다 실제로 동작하는 앵커 목차를 남긴다.
        linked = [d for d in candidates if d.select('a[href^="#"]')]
        if linked:
            for div in candidates:
                if div is not linked[0]:
                    div.decompose()
                    changes['duplicate_tocs'] += 1

    return (str(soup) if any(changes.values()) else content), changes
