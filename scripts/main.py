#!/usr/bin/env python3
"""
AutoBlog Engine v6.0 — AdSense 승인 최적화 + 품질 게이트
=========================================================
키워드 선택 → AI 글 생성 (멀티모델) → 품질 검증 → 이미지 삽입 (3중 폴백) →
제휴 링크 삽입 → AdSense HTML 최적화 → WordPress 발행 → Supabase 로깅

사용: python scripts/main.py [--dry-run] [--count 5] [--pipeline autoblog]
      python scripts/main.py --setup-pages          # 필수 페이지 자동 생성
"""

import os, sys, json, time, random, re, hashlib, logging, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── 경로 설정 ──
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

# ── 로깅 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("autoblog")

# ── 환경변수 ──
WP_URL = os.environ.get("WP_URL", "")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")
UNSPLASH_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")
GROK_KEY = os.environ.get("GROK_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SITE_ID = os.environ.get("SITE_ID", "site-1")

# 네이버 카페 API
NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
NAVER_REFRESH_TOKEN = os.environ.get("NAVER_REFRESH_TOKEN", "")
NAVER_CAFE_CLUBID = os.environ.get("NAVER_CAFE_CLUBID", "")
NAVER_CAFE_MENUID = os.environ.get("NAVER_CAFE_MENUID", "")

KST = timezone(timedelta(hours=9))


# ═══════════════════════════════════════════════════════
# 1. 키워드 관리
# ═══════════════════════════════════════════════════════
class KeywordManager:
    def __init__(self):
        self.kw_file = DATA / "keywords.json"
        self.used_file = DATA / "used_keywords.json"
        self.keywords = self._load(self.kw_file, {"keywords": []})
        self.used = self._load(self.used_file, [])

    def _load(self, path, default):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_used(self):
        with open(self.used_file, "w", encoding="utf-8") as f:
            json.dump(self.used, f, ensure_ascii=False, indent=2)

    def select(self, count=5, pipeline="autoblog", niche=""):
        """미사용 키워드 중 count개 선택 (niche로 카테고리 필터링)"""
        pool = self.keywords.get("keywords", [])
        available = [
            kw for kw in pool
            if kw.get("keyword") not in self.used
            and kw.get("pipeline", "autoblog") == pipeline
            and (not niche or kw.get("category", "") == niche)
        ]

        if niche:
            log.info(f"  니치 필터: '{niche}' -> {len(available)}개 키워드")

        if len(available) < count:
            log.warning(f"가용 키워드 {len(available)}개 (요청 {count}개)")
            count = len(available)

        # 타입별 비율: traffic 60%, conversion 30%, high_cpa 10%
        selected = []
        by_type = {}
        for kw in available:
            t = kw.get("type", "traffic")
            by_type.setdefault(t, []).append(kw)

        targets = {"traffic": max(1, int(count * 0.6)),
                   "conversion": max(1, int(count * 0.3)),
                   "high_cpa": max(0, count - max(1, int(count * 0.6)) - max(1, int(count * 0.3)))}

        for ktype, num in targets.items():
            pool_type = by_type.get(ktype, [])
            random.shuffle(pool_type)
            selected.extend(pool_type[:num])

        if len(selected) < count:
            remaining = [kw for kw in available if kw not in selected]
            random.shuffle(remaining)
            selected.extend(remaining[:count - len(selected)])

        return selected[:count]

    def mark_used(self, keyword):
        if keyword not in self.used:
            self.used.append(keyword)
            self._save_used()


# ═══════════════════════════════════════════════════════
# 1-B. 동적 키워드 생성 — 니치 기반 AI 키워드 (다양성 보장)
# ═══════════════════════════════════════════════════════

# 콘텐츠 앵글 (모든 니치에 공통 적용)
CONTENT_ANGLES = [
    "소개/개요", "활용법/사용 가이드", "수익화 방법", "비교/대안 분석",
    "조합 시너지", "월간 Top 순위", "카테고리별 순위", "초보 입문 가이드",
    "고급 활용 팁", "무료 vs 유료 비교", "트렌드/최신 동향", "실제 사례/후기",
    "문제 해결/트러블슈팅", "비용 절감 방법", "자동화 연계", "업데이트 소식",
]

# 콘텐츠 포맷
CONTENT_FORMATS = [
    "리스트형 (N가지 방법)", "비교표 (A vs B)", "스텝 가이드 (1단계→2단계)",
    "사례 연구 (실제 결과)", "Q&A형 (자주 묻는 질문)", "체크리스트형",
    "타임라인형 (변화 추이)", "인포그래픽형 (데이터 중심)",
]

# 타겟 독자
TARGET_READERS = [
    "직장인", "프리랜서", "학생", "마케터", "개발자", "크리에이터",
    "소상공인", "투자자", "주부", "시니어", "취준생", "부업러",
]

# 니치별 도메인 키워드 (AI가 조합에 사용)
NICHE_DOMAINS = {
    "ai-tools": ["ChatGPT", "Claude", "Gemini", "Midjourney", "Cursor", "NotebookLM", "Perplexity", "Copilot", "Suno", "Gamma", "Descript", "Runway"],
    "tech": ["노트북", "태블릿", "스마트폰", "모니터", "키보드", "마우스", "웹캠", "SSD", "공유기", "NAS"],
    "smart-home": ["스마트스피커", "로봇청소기", "스마트조명", "홈카메라", "스마트도어락", "에어컨자동화"],
    "pet": ["강아지", "고양이", "사료", "건강관리", "보험", "훈련", "용품"],
    "appliance": ["에어컨", "제습기", "공기청정기", "건조기", "식기세척기", "전기밥솥"],
    "beauty": ["스킨케어", "선크림", "파운데이션", "헤어케어", "뷰티디바이스", "성분분석"],
    "health": ["영양제", "다이어트", "운동루틴", "수면", "스트레스관리", "건강검진"],
    "baby": ["분유", "기저귀", "카시트", "유모차", "이유식", "장난감"],
    "fitness": ["홈트레이닝", "러닝머신", "덤벨", "요가매트", "스마트워치", "보충제"],
    "finance": ["적금", "ETF", "주식", "대출", "보험", "연금", "절세", "부동산"],
    "education": ["온라인강의", "자격증", "영어", "코딩교육", "독서법", "생산성앱"],
    "news-sbs": ["SBS뉴스", "경제", "정치", "사회", "국제"],
    "news-kbs": ["KBS뉴스", "시사", "경제동향"],
    "news-jtbc": ["JTBC뉴스", "팩트체크", "시사"],
    "news-mbc": ["MBC뉴스", "탐사보도", "시사"],
    "sns-trend": ["트위터트렌드", "인스타그램", "틱톡", "유튜브", "바이럴"],
    "top10-corp": ["삼성", "SK", "현대", "LG", "롯데", "포스코", "한화", "GS", "두산", "CJ"],
    "s-semi": ["삼성전자", "SK하이닉스", "TSMC", "ASML", "엔비디아", "HBM", "파운드리"],
    "s-ai": ["GPU", "LLM", "AI반도체", "엣지AI", "AI에이전트", "AI스타트업"],
    "s-defense": ["한화에어로", "LIG넥스원", "현대로템", "KAI", "방산수출"],
    "s-pharma": ["바이오시밀러", "셀트리온", "삼성바이오", "임상시험", "신약개발"],
    "s-chem": ["2차전지소재", "양극재", "전해액", "LG화학", "포스코케미칼"],
    "s-robot": ["협동로봇", "자율주행", "로봇청소기", "산업용로봇", "휴머노이드"],
    "s-security": ["제로트러스트", "클라우드보안", "랜섬웨어", "개인정보보호"],
    "s-enter": ["K-POP", "OTT", "드라마", "웹툰", "게임", "엔터주"],
    "s-ev": ["전기차", "배터리", "충전인프라", "LFP", "전고체"],
    "s-space": ["누리호", "스타링크", "위성통신", "우주관광"],
    "gov-support": ["정부보조금", "청년정책", "소상공인지원", "창업지원", "고용보험"],
    "tax-guide": ["종합소득세", "부가세", "연말정산", "세금환급", "절세전략"],
    "agency": ["고용노동부", "중소벤처기업부", "국세청", "금융위원회"],
    "event": ["CES", "MWC", "컨퍼런스", "세미나", "해커톤", "전시회"],
    "travel": ["항공권", "호텔", "패키지", "자유여행", "비자", "여행보험"],
    "keyword-collect": ["네이버트렌드", "구글트렌드", "키워드플래너", "롱테일키워드"],
    "niche-promo": ["브랜드스토리", "제품리뷰", "체험단", "인플루언서"],
    "brand": ["브랜딩", "콘텐츠마케팅", "SNS마케팅", "퍼포먼스마케팅"],
    "compare-land": ["가격비교", "스펙비교", "장단점분석", "사용자리뷰"],
}

KEYWORD_GEN_PROMPT = """당신은 블로그 키워드 전략가입니다.
아래 조건에 맞는 블로그 글 주제를 {count}개 생성하세요.

니치: {niche}
콘텐츠 앵글: {angle}
콘텐츠 포맷: {format}
타겟 독자: {target}
관련 도메인 키워드: {domains}

=== 반드시 지켜야 할 규칙 ===
1. 각 주제는 검색 가능한 구체적 키워드여야 합니다
2. 아래 "이미 발행된 제목"과 동일하거나 유사한 주제는 절대 금지
3. 고유 시드 "{seed}"를 활용하여 독창적인 관점을 포함하세요
4. 한국어로 작성, 2026년 기준 최신 정보

=== 이미 발행된 제목 (피해야 할 주제) ===
{used_titles}

=== 출력 형식 (JSON 배열만 출력) ===
[
  {{"keyword": "구체적 키워드", "intent": "informational 또는 transactional", "category": "블로그 카테고리명"}},
  ...
]
"""


class DynamicKeywordGenerator:
    """니치 기반 AI 동적 키워드 생성기 — 다양성 보장 알고리즘"""

    def __init__(self):
        self.used_titles = self._fetch_used_titles()

    def _fetch_used_titles(self):
        """Supabase에서 최근 발행 제목 가져오기 (중복 방지용)"""
        if not SUPABASE_URL or not SUPABASE_KEY:
            return []
        import requests
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/publish_logs?select=title&order=published_at.desc&limit=200",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=10
            )
            rows = resp.json()
            return [r["title"] for r in (rows or []) if r.get("title")]
        except Exception:
            return []

    def _get_dashboard_niches(self):
        """Supabase dashboard_config에서 선택된 니치 가져오기"""
        if not SUPABASE_URL or not SUPABASE_KEY:
            return []
        import requests
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=10
            )
            rows = resp.json()
            if rows and len(rows) > 0:
                settings = rows[0].get("settings", {})
                return settings.get("selNiches", [])
        except Exception:
            pass
        return []

    def generate(self, count=5):
        """선택된 니치에서 다양한 키워드 동적 생성"""
        # autoMode 체크
        if SUPABASE_URL and SUPABASE_KEY:
            import requests as _req
            try:
                _r = _req.get(f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                             headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=10)
                _rows = _r.json()
                if _rows and len(_rows) > 0:
                    _s = _rows[0].get("settings", {})
                    if _s.get("autoMode") is False:
                        log.info("  autoMode OFF — 정적 키워드 사용")
                        return None
            except Exception:
                pass

        niches = self._get_dashboard_niches()
        if not niches:
            log.info("  대시보드 니치 미선택 — 정적 키워드 폴백")
            return None

        log.info(f"  동적 키워드 생성 — 니치: {niches}")

        # 다양성 알고리즘: 니치별로 분배
        per_niche = max(1, count // len(niches))
        remainder = count - per_niche * len(niches)

        all_keywords = []
        for i, niche in enumerate(niches):
            n = per_niche + (1 if i < remainder else 0)
            kws = self._generate_for_niche(niche, n)
            all_keywords.extend(kws)

        random.shuffle(all_keywords)
        return all_keywords[:count]

    def _generate_for_niche(self, niche, count):
        """단일 니치에서 고유 키워드 생성"""
        # 다양성 요소 랜덤 선택
        angle = random.choice(CONTENT_ANGLES)
        fmt = random.choice(CONTENT_FORMATS)
        target = random.choice(TARGET_READERS)
        domains = NICHE_DOMAINS.get(niche, ["일반"])
        random.shuffle(domains)
        domain_str = ", ".join(domains[:5])

        # 고유 시드: site_id + niche + timestamp + random
        seed = hashlib.md5(
            f"{SITE_ID}-{niche}-{datetime.now(KST).isoformat()}-{random.random()}".encode()
        ).hexdigest()[:12]

        # 최근 발행 제목 (최대 30개)
        used_str = "\n".join(f"- {t}" for t in self.used_titles[:30]) or "(없음)"

        prompt = KEYWORD_GEN_PROMPT.format(
            count=count, niche=niche, angle=angle, format=fmt,
            target=target, domains=domain_str, seed=seed, used_titles=used_str
        )

        # AI로 키워드 생성 (가장 저렴한 모델 사용)
        keywords_json = self._call_ai(prompt)
        if not keywords_json:
            return []

        try:
            # JSON 추출
            text = keywords_json.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                result = []
                for kw in parsed:
                    kw["niche"] = niche
                    kw["pipeline"] = "autoblog"
                    kw["type"] = "traffic" if kw.get("intent") == "informational" else "conversion"
                    kw["_angle"] = angle
                    kw["_format"] = fmt
                    kw["_target"] = target
                    kw["_seed"] = seed
                    result.append(kw)
                log.info(f"  [{niche}] {len(result)}개 키워드 생성: {[k['keyword'][:20] for k in result]}")
                return result
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning(f"  [{niche}] 키워드 파싱 실패: {e}")
        return []

    def _call_ai(self, prompt):
        """가장 저렴한 AI 모델로 키워드 생성"""
        import requests

        # 1순위: Gemini (무료)
        if GEMINI_KEY:
            try:
                resp = requests.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"temperature": 1.0, "maxOutputTokens": 2000}},
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except Exception:
                pass

        # 2순위: DeepSeek (저렴)
        if DEEPSEEK_KEY:
            try:
                resp = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                    json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                          "temperature": 1.0, "max_tokens": 2000},
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

        # 3순위: Grok
        if GROK_KEY:
            try:
                resp = requests.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                    json={"model": "grok-3-mini", "messages": [{"role": "user", "content": prompt}],
                          "temperature": 1.0, "max_tokens": 2000},
                    timeout=30
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except Exception:
                pass

        log.warning("  키워드 생성 AI 호출 실패")
        return None


# ═══════════════════════════════════════════════════════
# 2. AI 글 생성 — 멀티모델 라우팅 + AdSense 최적화 프롬프트
# ═══════════════════════════════════════════════════════

# ── 한국어 프롬프트 (소비자 중심) ──
DRAFT_PROMPT_KO = """당신은 이 분야를 직접 경험하고 연구한 전문가입니다.
독자가 검색한 고민을 완벽히 해결하는 글을 씁니다.

키워드: {keyword}
검색의도: {intent}
카테고리: {category}
고유코드: {unique_seed}

=== 핵심 원칙: 독자 만족 최우선 ===
1. 제목: 독자의 실제 고민을 정확히 반영하는 제목. <title> 태그로 감싸기
   - "이걸 읽으면 내 문제가 해결되겠다"라는 확신을 주는 제목
2. 도입부: 3~4문장. 독자의 상황을 정확히 공감하고, 이 글이 줄 수 있는 가치를 약속
3. 본문: H2 소제목 5~7개, 각 소제목 아래 300~500자
   - 모든 주장에 구체적 수치/비교/출처 포함 (근거 없는 문장 금지)
   - 독자가 바로 실행할 수 있는 구체적 액션 아이템 포함
   - 다른 블로그에서 찾기 어려운 독자적 인사이트 1개 이상
   - <strong> 태그로 핵심 정보 강조 (최소 5개)
4. 마무리: 핵심 3줄 요약 + "지금 바로 할 수 있는 것" 구체적 안내
5. 톤: 친구에게 설명하듯 자연스럽고 따뜻한 대화체
   - "~입니다", "~한 것입니다" 같은 딱딱한 문체 금지
   - 독자를 존중하되 격식체보다 친근체
6. 분량: 4,000~7,000자 (빈 내용 없이 알차게)
7. 구성: 읽기 쉬운 깔끔한 정리 + 논리적 전개
   - 짧은 문단, 충분한 여백, 핵심 볼드 처리
   - 비교표(<table>)나 목록(<ul>/<ol>) 적극 활용

=== HTML 규칙 ===
- <title>글제목</title>을 최상단에
- <h2>, <p>, <strong>, <ul>/<ol>, <table> 사용
- <h1> 금지 (워드프레스 자동 생성)
- 각 <p>는 2~4문장, H2 사이 최소 2개 <p>
"""

POLISH_PROMPT_KO = """아래 블로그 초안을 독자가 감동할 수준으로 업그레이드하세요.

키워드: {keyword}

업그레이드 규칙:
1. AI 특유 표현 완전 제거:
   "다양한", "중요합니다", "살펴보겠습니다", "알아보겠습니다", "관심이 높아지고 있습니다"
   → 실제 사람이 쓴 것처럼 자연스러운 구어체로 100% 교체
2. 모든 문단에 구체적 수치/사례/비교 1개 이상 추가 (빈 주장 금지)
3. 문장 리듬: 짧은 문장(5어절)과 긴 문장(15어절) 혼합
4. 독자 공감: 질문→답변, 문제→해결 패턴으로 몰입감
5. 키워드를 H2 2~3개, 도입부, 마무리에 자연스럽게 배치
6. HTML 구조 유지, 내용만 퀄리티업
7. <strong> 최소 5개 이상
8. 4,000자 미만이면 실용적 정보를 보강하여 4,000자 이상으로

초안:
{draft}
"""

# ── 영문 프롬프트 (Consumer-first) ──
DRAFT_PROMPT_EN = """You are a hands-on expert who has personally researched and tested everything in this topic.
Write for a reader who Googled this problem and needs a real, actionable answer.

Keyword: {keyword}
Search Intent: {intent}
Category: {category}
Unique Code: {unique_seed}

=== Core Principle: Reader Value First ===
1. Title: Address the reader's actual problem. Wrap in <title> tag.
   - Make the reader think "This will solve my problem"
2. Introduction: 3-4 sentences. Empathize with reader's situation, promise clear value
3. Body: 5-7 H2 subheadings, 300-500 characters each section
   - Every claim backed by specific numbers, comparisons, or sources
   - Include actionable steps the reader can execute immediately
   - At least one unique insight not found on other top-ranking pages
   - Use <strong> for key information (minimum 5)
4. Conclusion: 3-line summary + specific "do this right now" action
5. Tone: Conversational yet authoritative — like explaining to a smart friend over coffee
   - Active voice preferred. No corporate jargon.
   - Vary sentence length: short punchy (5 words) mixed with detailed (20 words)
6. Length: 2,500-4,500 words (thorough, no fluff)
7. Structure: Clean formatting, logical flow, easy to scan
   - Short paragraphs, comparison tables, bulleted lists where helpful

=== HTML Rules ===
- <title>Post Title</title> at the top
- Use <h2>, <p>, <strong>, <ul>/<ol>, <table>
- No <h1> (WordPress auto-generates)
- Each <p> is 2-4 sentences. At least 2 <p> between H2s.
"""

POLISH_PROMPT_EN = """Upgrade this blog draft to a level that makes readers bookmark it.

Keyword: {keyword}

Upgrade rules:
1. Remove ALL AI-sounding phrases:
   "In conclusion", "It's worth noting", "Let's dive in", "In today's world",
   "Whether you're a... or a...", "Look no further", "When it comes to"
   → Replace with natural, human-written language
2. Every paragraph must have at least 1 specific number, case study, or comparison
3. Sentence rhythm: mix short punchy sentences with longer detailed ones
4. Reader engagement: question→answer, problem→solution patterns
5. Place keyword naturally in 2-3 H2s, intro, and conclusion
6. Keep HTML structure intact, upgrade content quality only
7. Minimum 5 <strong> tags
8. If under 2,500 words, add practical, actionable content to reach 2,500+

Draft:
{draft}
"""

# ── AdSense 승인 전용 프롬프트 (한국어) ──
ADSENSE_DRAFT_PROMPT_KO = """당신은 이 분야의 권위 있는 전문가입니다.
독자가 즐겨찾기에 저장할 만큼 완벽한 레퍼런스 글을 작성합니다.

키워드: {keyword}
검색의도: {intent}
카테고리: {category}
고유코드: {unique_seed}

=== AdSense 승인 품질 기준 ===
1. 제목: 전문적이면서 검색 친화적. <title> 태그
2. 도입부: 4~5문장. 이 주제가 왜 중요한지, 독자가 무엇을 얻을 수 있는지 명확히
3. 본문: H2 소제목 7~9개, 각 소제목 아래 400~600자
   - 모든 주장에 데이터 출처, 통계, 전문가 의견 포함
   - 비교표, 체크리스트, 단계별 가이드 등 실용적 구성
   - 독자가 바로 활용할 수 있는 액션 아이템 각 섹션마다 1개
   - <strong> 강조 최소 8개
   - 외부 광고성 링크 절대 금지
4. 마무리: 핵심 요약 5줄 + FAQ 3개 (자주 묻는 질문과 답변)
5. 톤: 신뢰감 있는 전문가 톤 + 읽기 쉬운 구성
6. 분량: 5,000~8,000자 (빈틈없이 상세하게)
7. 품질: 이 글 하나로 해당 주제의 모든 궁금증이 해결되는 수준

=== HTML 규칙 ===
- <title>글제목</title>을 최상단에
- <h2>, <h3>, <p>, <strong>, <ul>/<ol>, <table> 사용
- <h1> 금지
- 각 <p>는 2~3문장, H2 사이 최소 3개 <p>
- FAQ는 <h3>질문</h3><p>답변</p> 형식
"""

# ── AdSense 승인 전용 프롬프트 (영문) ──
ADSENSE_DRAFT_PROMPT_EN = """You are an authoritative expert in this field.
Write a definitive reference article that readers will bookmark and share.

Keyword: {keyword}
Search Intent: {intent}
Category: {category}
Unique Code: {unique_seed}

=== AdSense Approval Quality Standards ===
1. Title: Professional and search-friendly. Wrap in <title> tag.
2. Introduction: 4-5 sentences. Why this topic matters. What the reader will gain.
3. Body: 7-9 H2 subheadings, 400-600 chars per section
   - Every claim supported by data, statistics, or expert opinions
   - Comparison tables, checklists, step-by-step guides
   - Actionable takeaway in every section
   - Minimum 8 <strong> tags
   - Absolutely NO promotional or affiliate links
4. Conclusion: 5-line summary + 3 FAQs (with <h3> question / <p> answer)
5. Tone: Trustworthy expert voice + easy-to-read structure
6. Length: 3,000-5,000 words (comprehensive, no filler)
7. Quality: This single article should answer ALL questions about the topic

=== HTML Rules ===
- <title>Post Title</title> at the top
- Use <h2>, <h3>, <p>, <strong>, <ul>/<ol>, <table>
- No <h1>
- Each <p> is 2-3 sentences. At least 3 <p> between H2s.
- FAQ format: <h3>Question</h3><p>Answer</p>
"""

# ── 프롬프트 선택 함수 ──
def get_prompts(lang="ko", adsense_mode=False):
    """언어와 모드에 따라 적절한 프롬프트 반환"""
    if adsense_mode:
        if lang == "en":
            return ADSENSE_DRAFT_PROMPT_EN, POLISH_PROMPT_EN
        return ADSENSE_DRAFT_PROMPT_KO, POLISH_PROMPT_KO
    if lang == "en":
        return DRAFT_PROMPT_EN, POLISH_PROMPT_EN
    return DRAFT_PROMPT_KO, POLISH_PROMPT_KO


class ContentGenerator:
    """멀티모델 AI 글 생성기 — Grok→Gemini→DeepSeek (초안) + Claude (폴리싱)"""

    COST_RATES = {
        "grok-3-mini": {"input": 0.0003, "output": 0.0005},
        "grok-3": {"input": 0.003, "output": 0.015},
        "gemini-2.0-flash": {"input": 0.0001, "output": 0.0004},
        "gemini-2.5-flash-preview-05-20": {"input": 0.00015, "output": 0.0006},
        "deepseek-chat": {"input": 0.00014, "output": 0.00028},
        "claude-sonnet-4-20250514": {"input": 0.003, "output": 0.015},
        "claude-haiku-4-5-20241022": {"input": 0.001, "output": 0.005},
    }

    def generate(self, keyword, intent="informational", category="",
                 unique_seed="", lang="ko", adsense_mode=False,
                 preferred_draft=None, preferred_polish=None):
        """멀티모델 폴체인 + 언어/모드 분기 + 모델 선택 반영"""
        if not unique_seed:
            unique_seed = hashlib.md5(
                f"{SITE_ID}-{keyword}-{datetime.now(KST).isoformat()}-{random.random()}".encode()
            ).hexdigest()[:12]

        draft_tmpl, polish_tmpl = get_prompts(lang, adsense_mode)
        prompt = draft_tmpl.format(keyword=keyword, intent=intent, category=category, unique_seed=unique_seed)

        draft = None
        draft_model = None

        # 대시보드에서 선택한 모델을 1순위로 시도
        model_chain = []
        if preferred_draft:
            model_chain.append(preferred_draft)
        # 기본 폴체인 추가 (중복 제외)
        for m in ["grok", "gemini", "deepseek"]:
            if m not in [preferred_draft]:
                model_chain.append(m)

        for model_id in model_chain:
            if draft:
                break
            if model_id in ("grok", "grok-3", "grok-3-mini") and GROK_KEY:
                draft, draft_model = self._call_grok(prompt)
            elif model_id in ("gemini", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash") and GEMINI_KEY:
                draft, draft_model = self._call_gemini(prompt)
            elif model_id in ("deepseek", "deepseek-chat") and DEEPSEEK_KEY:
                draft, draft_model = self._call_deepseek(prompt)

        if not draft:
            log.error(f"모든 모델 실패: {keyword}")
            return None, 0, 0

        log.info(f"초안 완료 [{draft_model}] ({len(draft)}자)")
        draft_cost = self._estimate_cost(draft_model, prompt, draft)

        # 폴리싱 (preferred_polish가 'none'이면 스킵)
        if preferred_polish == "none":
            return draft, draft_cost, len(draft)

        if CLAUDE_KEY:
            polish_prompt = polish_tmpl.format(keyword=keyword, draft=draft)
            polished = self._call_claude_polish(polish_prompt)
            if polished:
                polish_cost = self._estimate_cost("claude-sonnet-4-20250514", polish_prompt, polished)
                log.info(f"폴리싱 완료 [Claude Sonnet] ({len(polished)}자)")
                return polished, draft_cost + polish_cost, len(polished)

        return draft, draft_cost, len(draft)

    def _call_grok(self, prompt):
        import requests
        try:
            log.info("Grok 초안 생성 중...")
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={"model": "grok-3-mini", "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.8, "max_tokens": 5000},
                timeout=180
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            self._log_cost("grok-3-mini", "xai", "content",
                          usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            return content, "grok-3-mini"
        except Exception as e:
            log.warning(f"Grok 실패: {e}")
            return None, None

    def _call_gemini(self, prompt):
        import requests
        try:
            log.info("Gemini 초안 생성 중...")
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0.8, "maxOutputTokens": 5000}},
                timeout=180
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["candidates"][0]["content"]["parts"][0]["text"]
            usage = data.get("usageMetadata", {})
            self._log_cost("gemini-2.0-flash", "google", "content",
                          usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
            return content, "gemini-2.0-flash"
        except Exception as e:
            log.warning(f"Gemini 실패: {e}")
            return None, None

    def _call_deepseek(self, prompt):
        import requests
        try:
            log.info("DeepSeek 초안 생성 중 (백업)...")
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.8, "max_tokens": 5000},
                timeout=180
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            self._log_cost("deepseek-chat", "deepseek", "content",
                          usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            return content, "deepseek-chat"
        except Exception as e:
            log.warning(f"DeepSeek 실패: {e}")
            return None, None

    def _call_claude_polish(self, prompt):
        import requests
        try:
            log.info("Claude Sonnet 폴리싱 중...")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"},
                json={"model": "claude-sonnet-4-20250514", "max_tokens": 6000,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=180
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            self._log_cost("claude-sonnet-4-20250514", "anthropic", "polish",
                          usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            return content
        except Exception as e:
            log.warning(f"Claude 폴리싱 실패 (초안 그대로 사용): {e}")
            return None

    def _estimate_cost(self, model, prompt_text, output_text):
        input_t = len(prompt_text) // 4
        output_t = len(output_text) // 4
        r = self.COST_RATES.get(model, {"input": 0.001, "output": 0.002})
        return (input_t / 1000 * r["input"]) + (output_t / 1000 * r["output"])

    def _log_cost(self, model, provider, purpose, input_t, output_t):
        r = self.COST_RATES.get(model, {"input": 0.001, "output": 0.002})
        cost_usd = (input_t / 1000 * r["input"]) + (output_t / 1000 * r["output"])
        cost_krw = int(cost_usd * 1450)
        log.info(f"  {model}: {input_t}+{output_t} tokens = ${cost_usd:.4f} (W{cost_krw})")

        if SUPABASE_URL and SUPABASE_KEY:
            try:
                import requests
                requests.post(
                    f"{SUPABASE_URL}/rest/v1/api_costs",
                    headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                             "Content-Type": "application/json", "Prefer": "return=minimal"},
                    json={"site_id": SITE_ID, "model": model, "provider": provider,
                          "purpose": purpose, "tokens_input": input_t, "tokens_output": output_t,
                          "cost_usd": round(cost_usd, 6), "cost_krw": cost_krw, "pipeline": "autoblog"},
                    timeout=10
                )
            except Exception:
                pass


# ═══════════════════════════════════════════════════════
# 3. 품질 게이트 — 발행 전 콘텐츠 검증 (100점 만점)
# ═══════════════════════════════════════════════════════
class QualityGate:
    """
    품질 채점 기준 (100점 만점):
    - 콘텐츠 길이: 25점 (4000자+ = 25, 3000+ = 20, 2000+ = 15, 1500+ = 10, 미만 = 5)
    - H2 소제목 수: 20점 (5~7개 = 20, 4개 = 17, 3개 = 12, 2개 = 8, 1개 이하 = 0)
    - 문단 품질: 15점 (평균 80~400자 = 15, 50~500자 = 10, 기타 = 5)
    - 이미지 포함: 15점 (있음 = 15, 없음 = 0)
    - 키워드 H2 포함: 10점 (H2에 키워드 존재 = 10, 없음 = 0)
    - <strong> 강조: 5점 (3개+ = 5, 1~2개 = 3, 없음 = 0)
    - CTA 존재: 5점 (행동유도 문구 있음 = 5, 없음 = 0)
    - HTML 구조: 5점 (h2+p 구조 정상 = 5, 비정상 = 0)
    """

    MIN_SCORE = 70

    def score(self, content, keyword, has_image=False):
        total = 0
        details = {}

        # 1. 콘텐츠 길이 (25점)
        length = len(content)
        if length >= 4000: pts = 25
        elif length >= 3000: pts = 20
        elif length >= 2000: pts = 15
        elif length >= 1500: pts = 10
        else: pts = 5
        total += pts
        details['length'] = f"{length}자 ({pts}점)"

        # 2. H2 소제목 수 (20점)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.IGNORECASE)
        h2_count = len(h2s)
        if 5 <= h2_count <= 7: pts = 20
        elif h2_count == 4: pts = 17
        elif h2_count == 3: pts = 12
        elif h2_count == 2 or h2_count == 8: pts = 8
        else: pts = 0
        total += pts
        details['h2_count'] = f"{h2_count}개 ({pts}점)"

        # 3. 문단 품질 (15점)
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.IGNORECASE | re.DOTALL)
        if paragraphs:
            avg_len = sum(len(re.sub(r'<[^>]+>', '', p)) for p in paragraphs) / len(paragraphs)
            if 80 <= avg_len <= 400: pts = 15
            elif 50 <= avg_len <= 500: pts = 10
            else: pts = 5
        else:
            avg_len = 0
            pts = 0
        total += pts
        details['paragraphs'] = f"{len(paragraphs)}개, 평균 {avg_len:.0f}자 ({pts}점)"

        # 4. 이미지 포함 (15점)
        img_in_content = '<img' in content.lower()
        pts = 15 if (has_image or img_in_content) else 0
        total += pts
        details['image'] = f"{'있음' if pts else '없음'} ({pts}점)"

        # 5. 키워드 H2 포함 (10점)
        kw_words = keyword.lower().split()
        kw_in_h2 = sum(1 for h2 in h2s if any(w in h2.lower() for w in kw_words if len(w) > 1))
        pts = 10 if kw_in_h2 >= 2 else (6 if kw_in_h2 == 1 else 0)
        total += pts
        details['keyword_h2'] = f"{kw_in_h2}개 H2 ({pts}점)"

        # 6. <strong> 강조 (5점)
        strong_count = len(re.findall(r'<strong>', content, re.IGNORECASE))
        pts = 5 if strong_count >= 3 else (3 if strong_count >= 1 else 0)
        total += pts
        details['strong'] = f"{strong_count}개 ({pts}점)"

        # 7. CTA 존재 (5점)
        cta_patterns = ['확인해', '시작해', '신청', '추천', '클릭', '바로가기', '지금', '놓치지']
        has_cta = any(p in content for p in cta_patterns)
        pts = 5 if has_cta else 0
        total += pts
        details['cta'] = f"{'있음' if has_cta else '없음'} ({pts}점)"

        # 8. HTML 구조 (5점)
        has_proper = '<h2' in content and '<p' in content and '</p>' in content
        pts = 5 if has_proper else 0
        total += pts
        details['structure'] = f"{'정상' if has_proper else '비정상'} ({pts}점)"

        return total, details

    def validate(self, content, keyword, has_image=False):
        score, details = self.score(content, keyword, has_image)
        passed = score >= self.MIN_SCORE
        log.info(f"  품질 점수: {score}/100 ({'PASS' if passed else 'FAIL'})")
        for k, v in details.items():
            log.info(f"    {k}: {v}")
        return passed, score, details


# ═══════════════════════════════════════════════════════
# 4. 이미지 삽입 — 3중 폴백 (Pexels → Pixabay → Unsplash)
# ═══════════════════════════════════════════════════════
class ImageManager:
    """이미지 3중 폴백: Pexels(1순위) → Pixabay(2순위) → Unsplash(백업)"""

    def fetch_image(self, keyword):
        """3중 폴백으로 이미지 검색"""
        # 1순위: Pexels (고품질 무료)
        if PEXELS_KEY:
            result = self._fetch_pexels(keyword)
            if result:
                return result

        # 2순위: Pixabay (대량 무료)
        if PIXABAY_KEY:
            result = self._fetch_pixabay(keyword)
            if result:
                return result

        # 3순위: Unsplash (백업)
        if UNSPLASH_KEY:
            result = self._fetch_unsplash(keyword)
            if result:
                return result

        log.warning(f"모든 이미지 API 실패: {keyword}")
        return None

    def _fetch_pexels(self, keyword):
        import requests
        try:
            log.info("  Pexels 이미지 검색 중...")
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": keyword, "per_page": 5, "orientation": "landscape", "size": "large"},
                timeout=10
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if photos:
                img = random.choice(photos[:3])
                log.info(f"  Pexels 이미지 확보: {img['photographer']}")
                return {
                    "url": img["src"]["large2x"],
                    "alt": keyword,
                    "credit": img["photographer"],
                    "link": img["photographer_url"],
                    "source": "Pexels"
                }
        except Exception as e:
            log.warning(f"  Pexels 실패: {e}")
        return None

    def _fetch_pixabay(self, keyword):
        import requests
        try:
            log.info("  Pixabay 이미지 검색 중...")
            resp = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_KEY, "q": keyword, "per_page": 5,
                    "orientation": "horizontal", "image_type": "photo",
                    "min_width": 1200, "safesearch": "true"
                },
                timeout=10
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            if hits:
                img = random.choice(hits[:3])
                log.info(f"  Pixabay 이미지 확보: {img.get('user', 'unknown')}")
                return {
                    "url": img["largeImageURL"],
                    "alt": keyword,
                    "credit": img.get("user", "Pixabay"),
                    "link": img.get("pageURL", "https://pixabay.com"),
                    "source": "Pixabay"
                }
        except Exception as e:
            log.warning(f"  Pixabay 실패: {e}")
        return None

    def _fetch_unsplash(self, keyword):
        import requests
        try:
            log.info("  Unsplash 이미지 검색 중 (백업)...")
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                params={"query": keyword, "per_page": 3, "orientation": "landscape"},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                img = random.choice(results[:3])
                log.info(f"  Unsplash 이미지 확보: {img['user']['name']}")
                return {
                    "url": img["urls"]["regular"],
                    "alt": img.get("alt_description", keyword),
                    "credit": img["user"]["name"],
                    "link": img["user"]["links"]["html"],
                    "source": "Unsplash"
                }
        except Exception as e:
            log.warning(f"  Unsplash 실패: {e}")
        return None

    def insert_image(self, content, image_data):
        """콘텐츠 첫 번째 H2 앞에 이미지 삽입"""
        if not image_data:
            return content, False, ""

        source = image_data.get("source", "Unknown")
        img_html = (
            f'<figure style="margin:24px 0">'
            f'<img src="{image_data["url"]}" alt="{image_data["alt"]}" '
            f'style="width:100%;border-radius:10px;box-shadow:0 2px 8px rgba(0,0,0,0.1)" loading="lazy"/>'
            f'<figcaption style="text-align:center;font-size:12px;color:#888;margin-top:8px;">'
            f'Photo by <a href="{image_data["link"]}?utm_source=autoblog" target="_blank">'
            f'{image_data["credit"]}</a> on {source}</figcaption>'
            f'</figure>'
        )

        if "<h2" in content:
            idx = content.index("<h2")
            return content[:idx] + img_html + content[idx:], True, source
        return img_html + content, True, source


# ═══════════════════════════════════════════════════════
# 5. 제휴 링크 삽입
# ═══════════════════════════════════════════════════════
class AffiliateManager:
    def __init__(self):
        self.links_file = DATA / "affiliates.json"
        self.links = self._load()

    def _load(self):
        if self.links_file.exists():
            with open(self.links_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"coupang": {}, "cpa": {}, "adsense_slots": []}

    def insert_links(self, content, keyword, category):
        coupang = self.links.get("coupang", {})
        matched_links = []

        for cat, links in coupang.items():
            if cat.lower() in keyword.lower() or cat.lower() in category.lower():
                if isinstance(links, list):
                    matched_links.extend(links)
                elif isinstance(links, str):
                    matched_links.append({"name": cat, "url": links})

        if matched_links:
            link_html = self._build_product_box(matched_links[:3])
            if "</h2>" in content:
                parts = content.rsplit("</h2>", 1)
                content = parts[0] + "</h2>" + link_html + parts[1]
            else:
                content += link_html

        return content, bool(matched_links)

    def _build_product_box(self, links):
        items = ""
        for link in links:
            name = link.get("name", "추천 상품")
            url = link.get("url", "#")
            if "YOUR_" in url:
                continue
            items += (
                f'<li style="margin:8px 0">'
                f'<a href="{url}" target="_blank" rel="nofollow sponsored" '
                f'style="color:#1a73e8;text-decoration:none;font-weight:600">'
                f'{name} 최저가 확인하기</a></li>'
            )

        if not items:
            return ""

        return (
            f'\n<div style="background:#f8f9ff;border:2px solid #dde3ff;'
            f'border-radius:12px;padding:20px;margin:24px 0">'
            f'<p style="font-weight:700;font-size:16px;margin:0 0 12px">추천 상품</p>'
            f'<ul style="list-style:none;padding:0;margin:0">{items}</ul>'
            f'<p style="font-size:11px;color:#999;margin:12px 0 0">'
            f'이 포스팅은 쿠팡 파트너스 활동의 일환으로, 일정액의 수수료를 제공받을 수 있습니다.</p>'
            f'</div>\n'
        )


# ═══════════════════════════════════════════════════════
# 6. AdSense HTML 최적화 — 발행 전 후처리
# ═══════════════════════════════════════════════════════
class AdSenseOptimizer:
    """발행 전 HTML 구조를 AdSense 친화적으로 정리"""

    def optimize(self, content):
        # 1. H2 사이에 충분한 간격 확보 (Ad Inserter 플러그인용)
        content = re.sub(
            r'(</h2>)\s*(<h2)',
            r'\1\n<p style="margin:12px 0">&nbsp;</p>\n\2',
            content
        )

        # 2. 빈 P 태그 정리
        content = re.sub(r'<p>\s*</p>', '', content)

        # 3. 연속된 <br> 정리
        content = re.sub(r'(<br\s*/?>){3,}', '<br/><br/>', content)

        # 4. 목차 스타일 개선 (이미 있으면 스킵)
        if '<ul' not in content[:500] and content.count('<h2') >= 4:
            toc = self._generate_toc(content)
            if toc:
                # 첫 번째 H2 앞에 목차 삽입
                if '<h2' in content:
                    idx = content.index('<h2')
                    content = content[:idx] + toc + content[idx:]

        return content

    def _generate_toc(self, content):
        """H2 기반 간단 목차 생성"""
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.IGNORECASE)
        if len(h2s) < 4:
            return ""

        items = ""
        for i, h2 in enumerate(h2s, 1):
            clean = re.sub(r'<[^>]+>', '', h2).strip()
            items += f'<li style="margin:4px 0"><a href="#section-{i}" style="color:#4a5568;text-decoration:none">{clean}</a></li>'

        return (
            f'<div style="background:#f1f5f9;border:1px solid #e2e8f0;border-radius:12px;'
            f'padding:16px 20px;margin:20px 0">'
            f'<p style="font-weight:700;font-size:14px;margin:0 0 8px;color:#1a1a2e">목차</p>'
            f'<ol style="margin:0;padding-left:20px;color:#4a5568;font-size:13px">{items}</ol>'
            f'</div>\n'
        )


# ═══════════════════════════════════════════════════════
# 7. WordPress 발행
# ═══════════════════════════════════════════════════════
class WordPressPublisher:
    def __init__(self):
        import base64
        self.url = WP_URL.rstrip("/")
        cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json"
        }

    def publish(self, title, content, category="", tags=None):
        import requests
        cat_id = self._get_or_create_category(category) if category else None

        post_data = {"title": title, "content": content, "status": "publish", "format": "standard"}
        if cat_id:
            post_data["categories"] = [cat_id]
        if tags:
            tag_ids = [self._get_or_create_tag(t) for t in tags[:5]]
            post_data["tags"] = [t for t in tag_ids if t]

        try:
            resp = requests.post(
                f"{self.url}/wp-json/wp/v2/posts", headers=self.headers,
                json=post_data, timeout=30
            )
            resp.raise_for_status()
            data = resp.json()
            return {"id": data["id"], "url": data.get("link", ""),
                    "title": data.get("title", {}).get("rendered", title), "status": "published"}
        except Exception as e:
            log.error(f"발행 실패: {e}")
            return {"status": "failed", "error": str(e)}

    def _get_or_create_category(self, name):
        import requests
        try:
            resp = requests.get(f"{self.url}/wp-json/wp/v2/categories",
                               headers=self.headers, params={"search": name, "per_page": 5}, timeout=10)
            for c in resp.json():
                if c["name"].lower() == name.lower():
                    return c["id"]
            resp = requests.post(f"{self.url}/wp-json/wp/v2/categories",
                                headers=self.headers, json={"name": name}, timeout=10)
            return resp.json().get("id")
        except Exception:
            return None

    def _get_or_create_tag(self, name):
        import requests
        try:
            resp = requests.get(f"{self.url}/wp-json/wp/v2/tags",
                               headers=self.headers, params={"search": name, "per_page": 5}, timeout=10)
            for t in resp.json():
                if t["name"].lower() == name.lower():
                    return t["id"]
            resp = requests.post(f"{self.url}/wp-json/wp/v2/tags",
                                headers=self.headers, json={"name": name}, timeout=10)
            return resp.json().get("id")
        except Exception:
            return None


# ═══════════════════════════════════════════════════════
# 8. 필수 페이지 자동 생성 (AdSense 승인용, 중복 방지)
# ═══════════════════════════════════════════════════════
class EssentialPagesCreator:
    """About/개인정보처리방침/연락처/면책고지/이용약관 자동 생성.
    이미 존재하는 페이지는 건너뜀 (slug 기반 중복 체크)."""

    PAGES = [
        {
            "slug": "about",
            "title": "소개",
            "content": """<h2>블로그 소개</h2>
<p>안녕하세요! <strong>{site_name}</strong>에 오신 것을 환영합니다.</p>
<p>저희 블로그는 독자 여러분께 유용하고 정확한 정보를 제공하기 위해 운영되고 있습니다.
전문 필진이 직접 조사하고 검증한 내용만을 다루며, 여러분의 일상에 실질적인 도움이 되는
양질의 콘텐츠를 만들기 위해 노력하고 있습니다.</p>
<h2>운영 목적</h2>
<p>복잡한 정보를 쉽고 명확하게 전달하여, 누구나 올바른 의사결정을 할 수 있도록 돕는 것이
저희의 목표입니다. 재테크, 금융, IT, 생활 정보 등 실용적인 분야를 중심으로 콘텐츠를
발행하고 있습니다.</p>
<h2>연락처</h2>
<p>문의사항이 있으시면 <a href="/contact">문의 페이지</a>를 통해 연락해 주세요.</p>"""
        },
        {
            "slug": "privacy-policy",
            "title": "개인정보처리방침",
            "content": """<h2>개인정보처리방침</h2>
<p><strong>{site_name}</strong>(이하 '사이트')은 이용자의 개인정보를 중요하게 생각하며,
「개인정보 보호법」을 준수하고 있습니다.</p>
<h3>1. 수집하는 개인정보 항목</h3>
<p>사이트는 서비스 제공을 위해 필요한 최소한의 개인정보를 수집합니다.</p>
<ul>
<li>댓글 작성 시: 이름, 이메일 주소</li>
<li>자동 수집: 접속 IP, 쿠키, 방문 일시, 서비스 이용 기록</li>
</ul>
<h3>2. 개인정보의 이용 목적</h3>
<ul>
<li>서비스 제공 및 운영</li>
<li>이용자 문의 응대</li>
<li>사이트 이용 통계 분석</li>
</ul>
<h3>3. 개인정보의 보유 및 이용 기간</h3>
<p>이용자의 개인정보는 수집 목적이 달성된 후 즉시 파기합니다.
단, 관련 법령에 의해 보존이 필요한 경우 해당 기간 동안 보관합니다.</p>
<h3>4. 쿠키(Cookie) 사용</h3>
<p>사이트는 이용자에게 맞춤형 서비스를 제공하기 위해 쿠키를 사용합니다.
이용자는 브라우저 설정에서 쿠키 허용을 관리할 수 있습니다.</p>
<h3>5. 광고</h3>
<p>사이트는 Google AdSense를 포함한 제3자 광고 서비스를 이용할 수 있습니다.
이러한 광고 서비스 제공업체는 사용자의 관심사에 맞는 광고를 게재하기 위해
쿠키를 사용할 수 있습니다.</p>
<h3>6. 개인정보 보호 책임자</h3>
<p>개인정보 관련 문의는 <a href="/contact">문의 페이지</a>를 통해 연락해 주세요.</p>
<p><em>시행일: {date}</em></p>"""
        },
        {
            "slug": "contact",
            "title": "문의하기",
            "content": """<h2>문의하기</h2>
<p>블로그에 대한 문의, 제안, 협업 요청 등 무엇이든 환영합니다.</p>
<h3>문의 방법</h3>
<p>아래 이메일로 연락해 주시면 빠른 시일 내에 답변 드리겠습니다.</p>
<p><strong>이메일:</strong> {email}</p>
<h3>문의 시 참고사항</h3>
<ul>
<li>광고 및 협업 관련 문의는 구체적인 내용을 함께 보내주세요.</li>
<li>콘텐츠 수정 요청은 해당 글의 URL을 포함해 주세요.</li>
<li>답변은 영업일 기준 1~3일 이내에 드립니다.</li>
</ul>"""
        },
        {
            "slug": "disclaimer",
            "title": "면책 고지",
            "content": """<h2>면책 고지 (Disclaimer)</h2>
<h3>정보의 정확성</h3>
<p><strong>{site_name}</strong>에서 제공하는 정보는 참고 목적으로 제공되며,
정확성이나 완전성을 보장하지 않습니다. 중요한 의사결정 시에는 반드시
전문가의 조언을 구하시기 바랍니다.</p>
<h3>제휴 링크 고지</h3>
<p>이 사이트의 일부 링크는 제휴(어필리에이트) 링크입니다.
이러한 링크를 통해 제품을 구매하시면 사이트 운영에 도움이 되는
소정의 수수료를 받을 수 있습니다. 이는 이용자에게 추가 비용을 발생시키지 않습니다.</p>
<p>이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다.</p>
<h3>외부 링크</h3>
<p>사이트에 포함된 외부 링크의 내용에 대해서는 책임을 지지 않습니다.</p>
<h3>투자 관련 면책</h3>
<p>본 사이트에서 제공하는 금융 관련 정보는 투자 권유가 아니며,
투자에 따른 손실에 대해 책임을 지지 않습니다.</p>
<p><em>시행일: {date}</em></p>"""
        },
        {
            "slug": "terms",
            "title": "이용약관",
            "content": """<h2>이용약관</h2>
<h3>제1조 (목적)</h3>
<p>이 약관은 <strong>{site_name}</strong>(이하 '사이트')이 제공하는 서비스의
이용 조건 및 절차에 관한 사항을 규정함을 목적으로 합니다.</p>
<h3>제2조 (이용자의 의무)</h3>
<ul>
<li>이용자는 사이트 이용 시 관련 법령을 준수해야 합니다.</li>
<li>타인의 개인정보를 도용하거나 허위 정보를 기재해서는 안 됩니다.</li>
<li>사이트의 콘텐츠를 무단으로 복제, 배포, 수정해서는 안 됩니다.</li>
</ul>
<h3>제3조 (저작권)</h3>
<p>사이트에 게시된 모든 콘텐츠의 저작권은 사이트 운영자에게 있습니다.
무단 전재 및 재배포를 금지합니다.</p>
<h3>제4조 (면책)</h3>
<p>사이트는 이용자가 사이트의 정보를 이용하여 발생한 손해에 대해
책임을 지지 않습니다.</p>
<h3>제5조 (약관의 변경)</h3>
<p>사이트는 필요 시 약관을 변경할 수 있으며, 변경된 약관은
사이트에 공지한 시점부터 효력이 발생합니다.</p>
<p><em>시행일: {date}</em></p>"""
        },
    ]

    def __init__(self):
        import base64
        self.url = WP_URL.rstrip("/")
        cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json"
        }

    def create_all(self, site_name="", email="contact@example.com"):
        import requests
        date_str = datetime.now(KST).strftime("%Y년 %m월 %d일")
        if not site_name:
            site_name = WP_URL.replace("https://", "").replace("http://", "").split("/")[0]

        created = []
        skipped = []
        failed = []

        for page in self.PAGES:
            slug = page["slug"]

            # ── 중복 체크: slug로 기존 페이지 검색 ──
            try:
                resp = requests.get(
                    f"{self.url}/wp-json/wp/v2/pages",
                    headers=self.headers,
                    params={"slug": slug, "per_page": 1, "status": "any"},
                    timeout=10
                )
                existing = resp.json()
                if isinstance(existing, list) and len(existing) > 0:
                    log.info(f"  '{page['title']}' ({slug}) 이미 존재 — 건너뜀")
                    skipped.append(page["title"])
                    continue
            except Exception as e:
                log.warning(f"  '{page['title']}' 중복 확인 실패, 생성 시도: {e}")

            # ── 페이지 생성 ──
            content = page["content"].format(
                site_name=site_name, date=date_str, email=email
            )

            try:
                resp = requests.post(
                    f"{self.url}/wp-json/wp/v2/pages",
                    headers=self.headers,
                    json={"title": page["title"], "slug": slug, "content": content, "status": "publish"},
                    timeout=15
                )
                resp.raise_for_status()
                url = resp.json().get("link", "")
                log.info(f"  '{page['title']}' 페이지 생성 완료: {url}")
                created.append(page["title"])
            except Exception as e:
                log.error(f"  '{page['title']}' 페이지 생성 실패: {e}")
                failed.append(page["title"])

        log.info(f"\n  필수 페이지 결과: 생성 {len(created)}개 / 이미 존재 {len(skipped)}개 / 실패 {len(failed)}개")
        return created, skipped, failed


# ═══════════════════════════════════════════════════════
# 9. Supabase 로깅
# ═══════════════════════════════════════════════════════
class SupabaseLogger:
    def __init__(self):
        self.url = SUPABASE_URL
        self.key = SUPABASE_KEY
        self.headers = {
            "apikey": self.key, "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json", "Prefer": "return=minimal"
        }

    def log_publish(self, data):
        if not self.url or not self.key:
            return
        import requests
        try:
            record = {
                "site_id": SITE_ID,
                "title": data.get("title", ""),
                "url": data.get("url", ""),
                "keyword": data.get("keyword", ""),
                "intent": data.get("intent", ""),
                "category": data.get("category", ""),
                "pipeline": data.get("pipeline", "autoblog"),
                "content_length": data.get("content_length", 0),
                "has_image": data.get("has_image", False),
                "image_tier": data.get("image_source", ""),
                "has_coupang": data.get("has_coupang", False),
                "quality_score": data.get("quality_score", 0),
                "sns_shared": json.dumps(data.get("sns_shared", [])),
                "status": data.get("status", "published"),
                "error_message": data.get("error_message", ""),
                "published_at": datetime.now(KST).isoformat(),
            }
            requests.post(
                f"{self.url}/rest/v1/publish_logs", headers=self.headers,
                json=record, timeout=10
            )
            log.info(f"  Supabase 로그 기록: {data.get('title', '')[:30]}")
        except Exception as e:
            log.warning(f"Supabase 로깅 실패: {e}")

    def log_alert(self, title, message, severity="warning", alert_type="info"):
        if not self.url or not self.key:
            return
        import requests
        try:
            requests.post(
                f"{self.url}/rest/v1/alerts", headers=self.headers,
                json={"site_id": SITE_ID, "alert_type": alert_type,
                      "severity": severity, "title": title, "message": message},
                timeout=10
            )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════
# 10. 네이버 카페 자동 공유
# ═══════════════════════════════════════════════════════
class NaverCafePublisher:
    """네이버 카페 API로 글 자동 공유.
    OAuth 2.0 Refresh Token으로 Access Token 자동 갱신."""

    TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
    CAFE_API = "https://openapi.naver.com/v1/cafe/{clubid}/menu/{menuid}/articles"

    def __init__(self):
        self.access_token = None
        self.clubid = NAVER_CAFE_CLUBID
        self.menuid = NAVER_CAFE_MENUID

    def is_configured(self):
        return all([NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NAVER_REFRESH_TOKEN,
                    self.clubid, self.menuid])

    def _refresh_access_token(self):
        """Refresh Token으로 새 Access Token 발급"""
        import requests
        try:
            resp = requests.post(self.TOKEN_URL, params={
                "grant_type": "refresh_token",
                "client_id": NAVER_CLIENT_ID,
                "client_secret": NAVER_CLIENT_SECRET,
                "refresh_token": NAVER_REFRESH_TOKEN,
            }, timeout=10)
            data = resp.json()
            if "access_token" in data:
                self.access_token = data["access_token"]
                log.info("  네이버 Access Token 갱신 완료")
                return True
            else:
                log.warning(f"  네이버 토큰 갱신 실패: {data.get('error_description', data)}")
                return False
        except Exception as e:
            log.warning(f"  네이버 토큰 갱신 실패: {e}")
            return False

    def publish(self, title, content, wp_url=""):
        """카페에 글 공유. HTML 콘텐츠를 그대로 전송."""
        import requests
        import urllib.parse

        if not self.is_configured():
            return None

        if not self.access_token:
            if not self._refresh_access_token():
                return None

        url = self.CAFE_API.format(clubid=self.clubid, menuid=self.menuid)

        # 원문 링크 추가
        footer = ""
        if wp_url:
            footer = (
                f'\n<p style="margin-top:24px;padding-top:16px;border-top:1px solid #eee;'
                f'font-size:13px;color:#888;">'
                f'원문: <a href="{wp_url}" target="_blank">{wp_url}</a></p>'
            )

        cafe_content = content + footer

        try:
            resp = requests.post(
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                data={
                    "subject": urllib.parse.quote(title),
                    "content": urllib.parse.quote(cafe_content),
                    "openyn": "true",
                    "searchopen": "true",
                    "replyyn": "true",
                },
                timeout=15
            )

            if resp.status_code == 200:
                result = resp.json()
                article_url = result.get("message", {}).get("result", {}).get("articleUrl", "")
                log.info(f"  네이버 카페 공유 완료: {article_url}")
                return article_url
            elif resp.status_code == 401:
                # 토큰 만료 → 재발급 후 재시도
                log.info("  네이버 토큰 만료, 재발급 시도...")
                if self._refresh_access_token():
                    return self.publish(title, content, wp_url)
                return None
            else:
                log.warning(f"  네이버 카페 공유 실패: {resp.status_code} {resp.text[:200]}")
                return None
        except Exception as e:
            log.warning(f"  네이버 카페 공유 실패: {e}")
            return None


# ═══════════════════════════════════════════════════════
# 10-B. Telegram 자동 공유
# ═══════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

class TelegramPublisher:
    def is_configured(self):
        return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

    def publish(self, title, keyword, wp_url=""):
        if not self.is_configured():
            return None
        import requests
        text = f"<b>{title}</b>\n\n#{keyword.replace(' ', '_')}\n\n{wp_url}" if wp_url else f"<b>{title}</b>\n\n#{keyword.replace(' ', '_')}"
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML",
                      "disable_web_page_preview": False},
                timeout=10
            )
            if resp.status_code == 200:
                log.info("  Telegram 공유 완료")
                return True
        except Exception as e:
            log.warning(f"  Telegram 공유 실패: {e}")
        return None


# ═══════════════════════════════════════════════════════
# 10-C. Discord 자동 공유
# ═══════════════════════════════════════════════════════
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

class DiscordPublisher:
    def is_configured(self):
        return bool(DISCORD_WEBHOOK_URL)

    def publish(self, title, keyword, wp_url=""):
        if not self.is_configured():
            return None
        import requests
        content = f"**{title}**\n> {keyword}\n{wp_url}" if wp_url else f"**{title}**\n> {keyword}"
        try:
            resp = requests.post(
                DISCORD_WEBHOOK_URL,
                json={"content": content},
                timeout=10
            )
            if resp.status_code in (200, 204):
                log.info("  Discord 공유 완료")
                return True
        except Exception as e:
            log.warning(f"  Discord 공유 실패: {e}")
        return None


# ═══════════════════════════════════════════════════════
# 11. API 상태 체크 — Supabase에 연결 상태 기록
# ═══════════════════════════════════════════════════════
def check_api_status():
    """모든 API 키 설정 상태를 확인하고 Supabase에 기록"""
    status = {
        "last_checked": datetime.now(KST).isoformat(),
        "wp": bool(WP_URL and WP_USER and WP_PASS),
        "deepseek": bool(DEEPSEEK_KEY),
        "claude": bool(CLAUDE_KEY),
        "grok": bool(GROK_KEY),
        "gemini": bool(GEMINI_KEY),
        "pexels": bool(PEXELS_KEY),
        "pixabay": bool(PIXABAY_KEY),
        "unsplash": bool(UNSPLASH_KEY),
        "supabase": bool(SUPABASE_URL and SUPABASE_KEY),
        "naver_cafe": bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET and NAVER_REFRESH_TOKEN
                           and NAVER_CAFE_CLUBID and NAVER_CAFE_MENUID),
        "telegram": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        "discord": bool(DISCORD_WEBHOOK_URL),
    }

    log.info("API 상태 체크:")
    for name, ok in status.items():
        if name == "last_checked":
            continue
        log.info(f"  {name}: {'OK' if ok else 'X'}")

    # Supabase에 기록
    if SUPABASE_URL and SUPABASE_KEY:
        import requests
        try:
            # 기존 설정 가져오기
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=10
            )
            existing = {}
            rows = resp.json()
            if rows and len(rows) > 0:
                existing = rows[0].get("settings", {})

            existing["api_status"] = status

            requests.patch(
                f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                headers={
                    "apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json", "Prefer": "return=minimal"
                },
                json={"settings": existing, "updated_at": datetime.now(KST).isoformat()},
                timeout=10
            )
            log.info("  API 상태 Supabase 기록 완료")
        except Exception as e:
            log.warning(f"  API 상태 기록 실패: {e}")

    return status


# ═══════════════════════════════════════════════════════
# 11-B. 콘텐츠 후처리 (Python 기반 — Claude 폴리싱 대체)
# ═══════════════════════════════════════════════════════
import re as _re


class ContentFormatter:
    """AI 폴리싱 없이 Python으로 HTML 스타일링 + AI 표현 치환"""

    # AI 특유 표현 -> 자연스러운 대체어 매핑
    AI_REPLACEMENTS = [
        ("살펴보도록 하겠습니다", "바로 확인해볼게요"),
        ("살펴보겠습니다", "확인해볼게요"),
        ("알아보도록 하겠습니다", "정리해드릴게요"),
        ("알아보겠습니다", "정리해볼게요"),
        ("말씀드리겠습니다", "알려드릴게요"),
        ("소개해드리겠습니다", "알려드릴게요"),
        ("확인해보겠습니다", "확인해볼게요"),
        ("설명드리겠습니다", "설명해드릴게요"),
        ("도움이 되셨으면 좋겠습니다", "도움이 되셨길 바라요"),
        ("도움이 되셨기를 바랍니다", "도움이 되셨길 바라요"),
        ("마무리하겠습니다", "마무리할게요"),
        ("시작하겠습니다", "시작해볼게요"),
    ]

    H2_STYLE = (
        'style="font-size:22px;font-weight:800;color:#1a1a1a;'
        'margin:40px 0 16px;padding-bottom:12px;border-bottom:3px solid #1a73e8"'
    )

    P_STYLE = 'style="line-height:1.9;color:#333;margin:16px 0;font-size:16px"'

    CTA_BOX = (
        '\n<div style="background:linear-gradient(135deg,#1a73e8,#4285f4);'
        'border-radius:12px;padding:24px 28px;margin:32px 0;text-align:center">\n'
        '<p style="color:#fff;font-size:18px;font-weight:700;margin:0 0 8px">'
        '\U0001f680 지금 바로 확인해보세요</p>\n'
        '<p style="color:rgba(255,255,255,0.9);margin:0;font-size:15px">'
        '위 내용을 참고해서 나에게 맞는 선택을 해보세요</p>\n'
        '</div>\n'
    )

    def format(self, content, keyword=""):
        """콘텐츠 후처리 파이프라인"""
        original_len = len(content)

        content = self._replace_ai_expressions(content)
        content = self._style_h2(content)
        content = self._style_p(content)
        content = self._ensure_cta(content)
        content = self._clean_empty_tags(content)

        changes = len(content) - original_len
        log.info(f"   H2 스타일링, p 스타일링, AI 표현 치환, 구조 검증 완료 ({changes:+d}자)")
        return content

    def _replace_ai_expressions(self, content):
        """AI 특유 표현을 자연스러운 구어체로 치환"""
        count = 0
        for old, new in self.AI_REPLACEMENTS:
            if old in content:
                content = content.replace(old, new)
                count += 1
        if count:
            log.info(f"   AI 표현 {count}개 치환")
        return content

    def _style_h2(self, content):
        """스타일 없는 H2에 프리미엄 스타일 적용"""
        def _replace_h2(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<h2', f'<h2 {self.H2_STYLE}', 1)

        return _re.sub(r'<h2[^>]*>', _replace_h2, content, flags=_re.IGNORECASE)

    def _style_p(self, content):
        """스타일 없는 p에 기본 스타일 적용"""
        def _replace_p(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<p', f'<p {self.P_STYLE}', 1)

        return _re.sub(r'<p(?:\s[^>]*)?>',  _replace_p, content, flags=_re.IGNORECASE)

    def _ensure_cta(self, content):
        """마무리에 CTA 박스가 없으면 추가"""
        cta_indicators = ['지금 바로', '시작하세요', '확인해보세요', '신청하세요']
        has_cta_box = any(
            ind in content[-500:] for ind in cta_indicators
        ) and '<div' in content[-800:]

        if has_cta_box:
            return content

        content = content.rstrip() + self.CTA_BOX
        log.info("   CTA 박스 추가")
        return content

    def _clean_empty_tags(self, content):
        """빈 태그, 불필요한 공백 정리"""
        content = _re.sub(r'<p[^>]*>\s*</p>', '', content)
        content = _re.sub(r'\n{3,}', '\n\n', content)
        return content


# ═══════════════════════════════════════════════════════
# 12. 메인 파이프라인
# ═══════════════════════════════════════════════════════
def extract_title(content):
    match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    if match:
        title = match.group(1).strip()
        content = re.sub(r"<title>.*?</title>", "", content, flags=re.IGNORECASE)
        return title, content
    match = re.search(r"<h2[^>]*>(.*?)</h2>", content, re.IGNORECASE)
    if match:
        return match.group(1).strip(), content
    return "자동 생성 글", content


def _get_site_config(site_id=None):
    """Supabase에서 사이트 설정 조회"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    import requests
    try:
        sid = site_id or SITE_ID
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/sites?id=eq.{sid}",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        rows = resp.json()
        if rows and len(rows) > 0:
            return rows[0]
    except Exception:
        pass
    return None


def _get_all_active_sites():
    """Supabase에서 active 상태인 모든 사이트 조회"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    import requests
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/sites?status=eq.active&order=created_at",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        return resp.json() or []
    except Exception:
        return []


def should_run_now():
    """대시보드 스케줄 설정과 현재 시각 비교. 해당 안 되면 False."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return True  # 설정 없으면 항상 실행
    import requests
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=10
        )
        rows = resp.json()
        if not rows or len(rows) == 0:
            return True
        settings = rows[0].get("settings", {})
        sel_days = settings.get("selDays")
        sel_times = settings.get("selTimes")
        if not sel_days and not sel_times:
            return True  # 스케줄 미설정 → 항상 실행

        tz_id = settings.get("tz", "KST")
        tz_offsets = {"KST": 9, "EST": -5, "CST": -6, "PST": -8}
        offset = tz_offsets.get(tz_id, 9)
        now = datetime.now(timezone(timedelta(hours=offset)))
        current_day = now.weekday()  # 0=월 ~ 6=일
        current_time = now.strftime("%H:%M")
        # 30분 윈도우 체크
        current_h, current_m = now.hour, now.minute
        slot = f"{current_h:02d}:{'00' if current_m < 30 else '30'}"

        if sel_days and current_day not in sel_days:
            log.info(f"스케줄 게이트: 오늘({current_day})은 발행일이 아닙니다 (설정: {sel_days})")
            return False
        if sel_times and slot not in sel_times:
            log.info(f"스케줄 게이트: 현재({slot})는 발행 시간이 아닙니다 (설정: {sel_times})")
            return False
        return True
    except Exception:
        return True  # 오류 시 안전하게 실행


def run_pipeline(count=5, dry_run=False, pipeline="autoblog", site_override=None, adsense_mode=False):
    """단일 사이트 파이프라인. site_override가 있으면 해당 사이트 설정 사용."""
    global SITE_ID, WP_URL, WP_USER, WP_PASS

    # 사이트 설정 로드
    if site_override:
        SITE_ID = site_override["id"]
        WP_URL = site_override.get("wp_url", "")
        cfg = site_override.get("config") or {}
        WP_USER = cfg.get("wp_username", WP_USER)
        WP_PASS = cfg.get("wp_app_password", WP_PASS)
        site_config = site_override
    else:
        site_config = _get_site_config()

    if site_config:
        if site_config.get("status") == "paused":
            log.info(f"[{SITE_ID}] 일시정지 상태 — 스킵")
            return
        db_target = site_config.get("daily_target")
        if db_target and count == 5:
            count = db_target

    # 글로벌 + 사이트별 설정 병합
    global_cfg = {}
    if SUPABASE_URL and SUPABASE_KEY:
        import requests as _req
        try:
            _r = _req.get(f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                         headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}, timeout=10)
            _rows = _r.json()
            if _rows and len(_rows) > 0:
                global_cfg = _rows[0].get("settings", {})
        except Exception:
            pass

    site_cfg = (site_config or {}).get("config") or {}
    ai_cfg = (site_config or {}).get("ai_config") or {}

    # 유효 설정: 사이트 > 글로벌 > 기본값
    effective_lang = site_cfg.get("lang", global_cfg.get("lang", "ko"))
    effective_draft_model = ai_cfg.get("draft_model", site_cfg.get("draft_model"))
    effective_polish_model = ai_cfg.get("polish_model", site_cfg.get("polish_model"))
    effective_adsense = adsense_mode or site_cfg.get("adsense_mode", False)

    if not WP_URL:
        log.error(f"[{SITE_ID}] WP_URL 없음 — 스킵")
        return

    log.info("=" * 60)
    log.info(f"AutoBlog Engine v6.0 — [{SITE_ID}] {count}편 발행")
    log.info(f"  WP: {WP_URL}")
    log.info(f"  파이프라인: {pipeline} | 드라이런: {dry_run}")
    log.info(f"  이미지: Pexels{'(O)' if PEXELS_KEY else '(X)'} → "
             f"Pixabay{'(O)' if PIXABAY_KEY else '(X)'} → "
             f"Unsplash{'(O)' if UNSPLASH_KEY else '(X)'}")
    log.info(f"  네이버 카페: {'(O)' if NAVER_REFRESH_TOKEN else '(X)'}")
    log.info("=" * 60)

    if not site_override:
        check_api_status()

    km = KeywordManager()
    dkg = DynamicKeywordGenerator()
    cg = ContentGenerator()
    cf = ContentFormatter()
    im = ImageManager()
    am = AffiliateManager()
    ao = AdSenseOptimizer()
    qg = QualityGate()
    nc = NaverCafePublisher()
    wp = WordPressPublisher()
    sb = SupabaseLogger()

    # 1순위: 대시보드 니치 기반 동적 키워드 생성
    keywords = dkg.generate(count=count)

    # 2순위: 정적 keywords.json 폴백
    if not keywords:
        log.info("  정적 키워드 폴백 사용")
        keywords = km.select(count=count, pipeline=pipeline)

    if not keywords:
        log.error("사용 가능한 키워드 없음!")
        sb.log_alert("키워드 소진", "사용 가능한 키워드가 없습니다.", "critical", "keyword_exhausted")
        return

    log.info(f"선택된 키워드 {len(keywords)}개:")
    for kw in keywords:
        log.info(f"  [{kw.get('type', 'traffic')}] {kw['keyword']}")

    success = 0
    fail = 0

    for i, kw_data in enumerate(keywords, 1):
        keyword = kw_data["keyword"]
        intent = kw_data.get("intent", "informational")
        category = kw_data.get("category", "")
        kw_type = kw_data.get("type", "traffic")
        unique_seed = kw_data.get("_seed", "")

        log.info(f"\n{'='*50}")
        log.info(f"[{i}/{len(keywords)}] '{keyword}' ({kw_type})")
        if kw_data.get("_angle"):
            log.info(f"  앵글: {kw_data['_angle']} / 포맷: {kw_data.get('_format', '')} / 타겟: {kw_data.get('_target', '')}")
        log.info(f"{'='*50}")

        # Step 1: AI 글 생성
        content, cost_usd, content_length = cg.generate(
            keyword, intent, category, unique_seed,
            lang=effective_lang, adsense_mode=effective_adsense,
            preferred_draft=effective_draft_model, preferred_polish=effective_polish_model
        )
        if not content:
            fail += 1
            sb.log_publish({"keyword": keyword, "status": "failed",
                           "error_message": "AI 글 생성 실패", "pipeline": pipeline})
            continue

        log.info(f"글 생성 완료 ({content_length}자)")

        # Step 1.5: Python 후처리 (스타일링 + AI 표현 치환)
        content = cf.format(content, keyword=keyword)
        content_length = len(content)

        # Step 2: 제목 추출
        title, content = extract_title(content)
        log.info(f"제목: {title}")

        # Step 3: 이미지 삽입 (3중 폴백)
        img_data = im.fetch_image(keyword)
        content, has_image, image_source = im.insert_image(content, img_data)
        if has_image:
            log.info(f"이미지 삽입 완료 [{image_source}]")

        # Step 4: 제휴 링크 삽입
        has_coupang = False
        if not effective_adsense:  # AdSense 승인 모드에서는 제휴 링크 비활성화
            content, has_coupang = am.insert_links(content, keyword, category)
            if has_coupang:
                log.info("제휴 링크 삽입 완료")
        else:
            log.info("  AdSense 모드 — 제휴 링크 스킵")

        # Step 5: AdSense HTML 최적화
        content = ao.optimize(content)
        log.info("AdSense HTML 최적화 완료")

        # Step 6: 품질 검증 (AdSense 모드: 85점, 일반: 70점)
        min_score = 85 if effective_adsense else qg.MIN_SCORE
        passed, quality_score, q_details = qg.validate(content, keyword, has_image)
        passed = quality_score >= min_score

        # AdSense 모드: 미달 시 최대 2회 재생성
        if not passed and effective_adsense:
            for retry in range(2):
                log.info(f"  AdSense 모드 재생성 ({retry+1}/2) — {quality_score}점 < {min_score}점")
                content2, cost2, len2 = cg.generate(
                    keyword, intent, category, "",
                    lang=effective_lang, adsense_mode=True,
                    preferred_draft=effective_draft_model, preferred_polish=effective_polish_model
                )
                if content2:
                    title2, content2 = extract_title(content2)
                    if img_data:
                        content2, _, _ = im.insert_image(content2, img_data)
                    content2 = ao.optimize(content2)
                    _, qs2, _ = qg.validate(content2, keyword, has_image)
                    if qs2 >= min_score:
                        content, title, quality_score = content2, title2, qs2
                        content_length = len2
                        cost_usd += cost2
                        passed = True
                        log.info(f"  재생성 성공 — {qs2}점")
                        break
                    quality_score = max(quality_score, qs2)

        if not passed:
            log.warning(f"품질 {'미달' if not effective_adsense else '미달(재생성 실패)'} ({quality_score}/{min_score}) — 발행 진행")
            sb.log_alert(
                f"품질 미달: {keyword}",
                f"점수 {quality_score}/{min_score}. 항목: {json.dumps(q_details, ensure_ascii=False)[:300]}",
                "warning", "quality_low"
            )

        # Step 7: 발행
        if dry_run:
            log.info(f"[DRY RUN] 발행 스킵: {title} (품질: {quality_score}/100)")
            km.mark_used(keyword)
            success += 1
            continue

        result = wp.publish(title, content, category=category,
                           tags=[keyword, category] if category else [keyword])

        if result["status"] == "published":
            log.info(f"발행 성공: {result.get('url', '')} (품질: {quality_score}/100)")
            km.mark_used(keyword)
            success += 1

            # Step 8: SNS 자동 공유 (snsOn 토글 반영)
            sns_on = global_cfg.get("snsOn", {})
            sns_shared = []
            wp_link = result.get("url", "")

            if nc.is_configured() and sns_on.get("naver_cafe", True):
                cafe_url = nc.publish(title, content, wp_url=wp_link)
                if cafe_url:
                    sns_shared.append("naver_cafe")

            tg = TelegramPublisher()
            if tg.is_configured() and sns_on.get("telegram", True):
                if tg.publish(title, keyword, wp_link):
                    sns_shared.append("telegram")

            dc = DiscordPublisher()
            if dc.is_configured() and sns_on.get("discord", True):
                if dc.publish(title, keyword, wp_link):
                    sns_shared.append("discord")

            sb.log_publish({
                "title": title, "url": result.get("url", ""),
                "keyword": keyword, "intent": intent, "category": category,
                "pipeline": pipeline, "content_length": content_length,
                "has_image": has_image, "image_source": image_source,
                "has_coupang": has_coupang,
                "quality_score": quality_score,
                "sns_shared": sns_shared,
                "status": "published"
            })
        else:
            fail += 1
            error_msg = result.get("error", "Unknown error")
            log.error(f"발행 실패: {error_msg}")

            sb.log_publish({
                "title": title, "keyword": keyword, "pipeline": pipeline,
                "quality_score": quality_score,
                "status": "failed", "error_message": error_msg[:500]
            })

            if fail >= 3:
                sb.log_alert(f"연속 발행 실패 {fail}건",
                            f"최근 키워드: {keyword}\n에러: {error_msg[:200]}",
                            "critical", "publish_fail")

        delay = random.randint(5, 15)
        log.info(f"  {delay}초 대기...")
        time.sleep(delay)

    log.info(f"\n{'='*60}")
    log.info(f"실행 결과: 성공 {success}편 / 실패 {fail}편 / 총 {len(keywords)}편")
    log.info(f"{'='*60}")

    _git_commit_used()


def _git_commit_used():
    try:
        import subprocess
        subprocess.run(["git", "config", "user.email", "bot@autoblog.com"], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AutoBlog Bot"], cwd=ROOT, capture_output=True)
        subprocess.run(["git", "add", "data/used_keywords.json"], cwd=ROOT, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", f"chore: update used keywords {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}"],
            cwd=ROOT, capture_output=True, text=True
        )
        if result.returncode == 0:
            subprocess.run(["git", "push"], cwd=ROOT, capture_output=True)
            log.info("사용 키워드 Git push 완료")
    except Exception as e:
        log.warning(f"Git commit 실패 (무시): {e}")


# ═══════════════════════════════════════════════════════
# 멀티사이트 실행
# ═══════════════════════════════════════════════════════
def run_all_sites(count=5, dry_run=False, pipeline="autoblog", adsense_mode=False):
    """Supabase에서 모든 active 사이트를 조회하고 순차적으로 파이프라인 실행"""
    check_api_status()

    sites = _get_all_active_sites()
    if not sites:
        log.error("active 상태인 사이트가 없습니다.")
        return

    log.info("=" * 60)
    log.info(f"멀티사이트 모드 — {len(sites)}개 사이트")
    for s in sites:
        log.info(f"  [{s['id']}] {s.get('name', '?')} ({s.get('domain', '?')})")
    log.info("=" * 60)

    for site in sites:
        cfg = site.get("config") or {}
        wp_url = site.get("wp_url", "") or WP_URL
        wp_user = cfg.get("wp_username", "") or WP_USER
        wp_pass = cfg.get("wp_app_password", "") or WP_PASS

        if not wp_url or not wp_user or not wp_pass:
            log.warning(f"[{site['id']}] WP 인증정보 미설정 — 스킵")
            log.warning(f"  대시보드 설정 탭에서 WP URL/인증정보를 입력하거나 환경변수를 설정하세요")
            continue

        log.info(f"\n{'#'*60}")
        log.info(f"# 사이트: [{site['id']}] {site.get('name', '')}")
        log.info(f"{'#'*60}")

        try:
            run_pipeline(count=count, dry_run=dry_run, pipeline=pipeline, site_override=site, adsense_mode=adsense_mode)
        except Exception as e:
            log.error(f"[{site['id']}] 파이프라인 오류: {e}")

    _git_commit_used()
    log.info(f"\n{'='*60}")
    log.info(f"멀티사이트 실행 완료 — {len(sites)}개 사이트 처리")
    log.info(f"{'='*60}")


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="AutoBlog Engine v6.0")
    parser.add_argument("--count", type=int, default=5, help="발행 편수 (사이트별)")
    parser.add_argument("--dry-run", action="store_true", help="발행 없이 테스트")
    parser.add_argument("--pipeline", default="autoblog", help="파이프라인 (autoblog/hotdeal/promo)")
    parser.add_argument("--all-sites", action="store_true", help="Supabase 등록된 모든 active 사이트에 발행")
    parser.add_argument("--adsense-mode", action="store_true", help="AdSense 승인용 고품질 모드 (85점+, 재생성)")
    parser.add_argument("--site-id", default="", help="특정 사이트 ID 지정 (기본: SITE_ID 환경변수)")
    parser.add_argument("--setup-pages", action="store_true", help="AdSense 필수 페이지 자동 생성")
    parser.add_argument("--check-status", action="store_true", help="API 연결 상태 체크 → Supabase 기록")
    parser.add_argument("--site-name", default="", help="사이트 이름 (필수 페이지용)")
    parser.add_argument("--email", default="contact@example.com", help="연락처 이메일")
    parser.add_argument("--niche", default="", help="니치/카테고리 필터 (재테크, 투자, 대출 등)")
    parser.add_argument("--polish", action="store_true", help="Claude AI 폴리싱 활성화 (비용 증가)")
    args = parser.parse_args()

    # API 상태 체크 모드
    if args.check_status:
        check_api_status()
        sys.exit(0)

    # 필수 페이지 생성 모드
    if args.setup_pages:
        if not WP_URL or not WP_USER or not WP_PASS:
            log.error("WP_URL, WP_USERNAME, WP_APP_PASSWORD 환경변수 필요")
            sys.exit(1)
        epc = EssentialPagesCreator()
        epc.create_all(site_name=args.site_name, email=args.email)
        sys.exit(0)

    if not (DEEPSEEK_KEY or GROK_KEY or GEMINI_KEY):
        log.error("AI API 키가 하나도 없음 (DEEPSEEK/GROK/GEMINI 중 1개 필요)")
        sys.exit(1)

    # 멀티사이트 모드
    if args.all_sites:
        run_all_sites(count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                      adsense_mode=args.adsense_mode)
        return

    # 특정 사이트 지정
    if args.site_id:
        global SITE_ID
        SITE_ID = args.site_id
        site = _get_site_config(args.site_id)
        if site:
            run_pipeline(count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                         site_override=site, adsense_mode=args.adsense_mode)
        else:
            log.error(f"사이트 '{args.site_id}' 를 찾을 수 없습니다.")
            sys.exit(1)
        return

    # 단일 사이트 모드 (환경변수 기반)
    if not WP_URL:
        log.error("WP_URL 환경변수 없음. --all-sites 또는 --site-id를 사용하세요.")
        sys.exit(1)
    run_pipeline(count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                 adsense_mode=args.adsense_mode)


if __name__ == "__main__":
    main()
