"""Reviewable site information templates. Never an automatic legal/policy certification."""
import re
from html import escape
from requests import RequestException


def build_pages(site_name, owner, description, email):
    values = (site_name, owner, description, email)
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError("사이트명, 운영자명, 소개, 연락처 이메일이 필요합니다.")
    if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", email):
        raise ValueError("연락처 이메일 형식을 확인하세요.")
    if email.rsplit("@", 1)[1].lower() in {"example.com", "example.org", "example.net", "localhost"}:
        raise ValueError("예시 이메일로 페이지를 생성할 수 없습니다.")
    name, owner, desc, email = [escape(v.strip(), quote=True) for v in values]
    contact = f'<a href="mailto:{email}">{email}</a>'
    pages = [
        ("about", "소개", f'''<h2>{name}</h2><p>{desc}</p>
<h2>운영자</h2><p>{owner}</p>
<h2>콘텐츠 작성 원칙</h2><p>자료의 기준일과 출처, 판단의 근거와 한계를 함께 설명하는 것을 목표로 합니다.
실제 사용 기록이 없는 내용은 체험담으로 표현하지 않으며, 가정은 예시로 구분합니다.</p>
<p>오류 제보와 정정 요청: {contact}</p>'''),
        ("contact", "문의하기", f'''<h2>문의 및 오류 제보</h2><p>운영자: {owner}</p>
<p>{contact}</p><p>문제가 있는 글의 주소와 수정이 필요한 부분, 확인 가능한 원문을 알려주세요.
민감한 개인정보나 비밀번호는 보내지 마세요.</p>'''),
        ("privacy-policy", "개인정보처리방침", f'''<h2>개인정보처리방침 검토 초안</h2>
<p>운영자: {owner} / 사이트: {name} / 문의: {contact}</p>
<h3>서비스별 개인정보 처리</h3><p>[확인 필요] 실제로 사용하는 댓글, 문의, 통계, 호스팅 서비스를 나열하고
각 서비스의 수집 항목, 목적, 보유 기간, 처리업체와 삭제 요청 방법을 기재하세요.
사용하지 않는 서비스는 삭제하세요.</p>
<h3>Google 광고와 쿠키</h3><p>Google 광고를 사용하는 경우 Google을 포함한 제3자 업체는
이 사이트 또는 다른 사이트의 이전 방문 기록에 기반한 광고를 제공하기 위해 쿠키를 사용할 수 있습니다.
Google과 파트너는 광고 쿠키를 이용하여 이 사이트 및 다른 인터넷 사이트 방문에 기반한 광고를 제공합니다.</p>
<p>이용자는 <a href="https://www.google.com/settings/ads">Google 광고 설정</a>에서 맞춤 광고를 해제하거나,
<a href="https://www.aboutads.info/choices/">제3자 맞춤 광고 선택 페이지</a>를 이용할 수 있습니다.
<a href="https://policies.google.com/technologies/ads">Google의 광고 기술 안내</a>도 확인할 수 있습니다.</p>
<p>[확인 필요] 실제 활성화된 다른 광고 업체 및 광고 네트워크의 정책과 해제 링크를 추가하세요.
서비스 대상 지역에 필요한 동의 화면이 실제 작동하는지 확인하세요.</p>
<h3>시행일 및 권리 행사</h3><p>[확인 필요] 시행일과 열람·삭제·동의 철회 절차를 확정하세요.</p>'''),
        ("editorial-policy", "콘텐츠 작성 및 정정 원칙", f'''<h2>작성 원칙</h2>
<p>AI는 초안 작성과 자료 정리에 활용할 수 있습니다. 공개 전에는 운영자가 원문과 수치,
이미지 사용 권한, 독자에게 필요한 설명을 확인하는 절차를 적용합니다.</p>
<p>AI 생성 결과나 내부 점수는 사실 확인을 대신하지 않습니다. 개인 체험은 실제 기록이 있을 때만 표시합니다.</p>
<h2>광고 및 제휴</h2><p>대가가 있는 링크나 협찬이 포함되면 해당 콘텐츠에서 확인할 수 있도록 표시합니다.</p>
<h2>정정 요청</h2><p>{contact}으로 글 주소와 근거를 보내주세요.
중요한 정정은 해당 글에 변경 내용과 날짜를 표시하는 것을 원칙으로 합니다.</p>'''),
    ]
    return [{"slug": slug, "title": title, "content": content, "status": "draft"}
            for slug, title, content in pages]


def create_missing_drafts(url, headers, pages, session):
    """Preserve existing pages verbatim. On lookup failure, do not attempt a write."""
    created, skipped, failed = [], [], []
    for page in pages:
        try:
            response = session.get(f"{url}/wp-json/wp/v2/pages", headers=headers,
                                   params={"slug": page["slug"], "status": "any", "per_page": 1}, timeout=15)
            response.raise_for_status()
            existing = response.json()
            if not isinstance(existing, list):
                raise ValueError("Invalid page lookup")
            if existing:
                skipped.append(page["slug"])
                continue
            response = session.post(f"{url}/wp-json/wp/v2/pages", headers=headers,
                                    json={**page, "status": "draft"}, timeout=15)
            response.raise_for_status()
            if response.json().get("status") != "draft":
                raise ValueError("Unexpected page status")
            created.append(page["slug"])
        except (ValueError, OSError, RequestException):
            # Response bodies and authentication details never enter logs.
            failed.append(page["slug"])
    return created, skipped, failed
