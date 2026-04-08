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
    def __init__(self, site_id=None):
        # 사이트별 키워드 파일: keywords_{domain}.json → keywords.json 폴백
        self.kw_file = self._resolve_kw_file(site_id)
        self.used_file = DATA / "used_keywords.json"
        self.keywords = self._load(self.kw_file, {"keywords": []})
        self.used = self._load(self.used_file, [])
        log.info(f"  키워드 파일: {self.kw_file.name} ({len(self.keywords.get('keywords', []))}개)")

    def _resolve_kw_file(self, site_id):
        """사이트별 키워드 파일 탐색: keywords_{도메인}.json → keywords.json"""
        if site_id:
            # site_id에서 도메인 추출 시도 (Supabase site_override 기반)
            # 또는 WP_URL에서 도메인 추출
            domain = WP_URL.replace("https://", "").replace("http://", "").split("/")[0].replace("www.", "")
            domain_slug = domain.replace(".", "_").replace("-", "_")  # bomissu.com → bomissu_com
            # bomissu.com → keywords_bomissu.json 패턴
            domain_prefix = domain.split(".")[0]  # bomissu
            for pattern in [f"keywords_{domain_prefix}.json", f"keywords_{domain_slug}.json"]:
                candidate = DATA / pattern
                if candidate.exists():
                    return candidate
        return DATA / "keywords.json"

    def _load(self, path, default):
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_used(self):
        with open(self.used_file, "w", encoding="utf-8") as f:
            json.dump(self.used, f, ensure_ascii=False, indent=2)

    def select(self, count=5, pipeline="autoblog", niche="", kw_mix=None):
        """미사용 키워드 중 count개 선택. 소진 시: AI 동적 생성 → 재활용 순서로 폴백."""
        pool = self.keywords.get("keywords", [])
        available = [
            kw for kw in pool
            if kw.get("keyword") not in self.used
            and kw.get("pipeline", "autoblog") == pipeline
            and (not niche or kw.get("category", "") == niche)
        ]

        if niche:
            log.info(f"  니치 필터: '{niche}' -> {len(available)}개 키워드")

        # 키워드 부족 시: 1차 AI 동적 생성 시도, 2차 재활용
        if len(available) < count:
            # 1차: AI 동적 키워드 생성 (니치 지정 시)
            need = count - len(available)
            ai_niche = niche if niche else None
            if ai_niche:
                ai_keywords = self._generate_for_niche(ai_niche, need)
                if ai_keywords:
                    log.info(f"🤖 AI 동적 키워드 {len(ai_keywords)}개 생성 ({ai_niche})")
                    available.extend(ai_keywords)

            # 2차: 그래도 부족하면 used 초기화 후 재활용
            if len(available) < count and len(pool) > 0:
                pipeline_pool = [kw for kw in pool
                                if kw.get("pipeline", "autoblog") == pipeline
                                and (not niche or kw.get("category", "") == niche)]
                if pipeline_pool:
                    log.info(f"♻️ 키워드 재활용 (재사용 {len(pipeline_pool)}개)")
                    recycle_kws = {kw.get("keyword") for kw in pipeline_pool}
                    self.used = [u for u in self.used if u not in recycle_kws]
                    self._save_used()
                    recycled = [kw for kw in pipeline_pool if kw not in available]
                    available.extend(recycled)

        if len(available) < count:
            log.warning(f"가용 키워드 {len(available)}개 (요청 {count}개)")
            count = len(available)

        # 타입별 비율: stage kw_mix 또는 기본값
        selected = []
        by_type = {}
        for kw in available:
            t = kw.get("type", "traffic")
            by_type.setdefault(t, []).append(kw)

        mix = kw_mix or {"traffic": 0.6, "conversion": 0.3, "high_cpa": 0.1}
        targets = {
            "traffic": max(1, int(count * mix["traffic"])),
            "conversion": max(0, int(count * mix["conversion"])),
            "high_cpa": max(0, count - max(1, int(count * mix["traffic"])) - max(0, int(count * mix["conversion"])))
        }

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

    # ── 카니발라이제이션 검사 ──
    def check_cannibalization(self, keyword, threshold=0.6):
        """새 키워드와 기존 사용 키워드 간 Jaccard 유사도 비교.
        threshold 이상이면 (유사 키워드, 점수) 리스트 반환."""
        new_words = set(keyword.lower().split())
        if len(new_words) < 2:
            return []

        conflicts = []
        for used_kw in self.used:
            # used_keywords.json에 해시 프리픽스가 붙은 항목 제거
            clean = used_kw.split(" ", 1)[-1] if " " in used_kw and len(used_kw.split(" ", 1)[0]) == 12 else used_kw
            used_words = set(clean.lower().split())
            if len(used_words) < 2:
                continue
            intersection = new_words & used_words
            union = new_words | used_words
            jaccard = len(intersection) / len(union) if union else 0
            if jaccard >= threshold:
                conflicts.append((clean, round(jaccard, 2)))

        return sorted(conflicts, key=lambda x: x[1], reverse=True)


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

# 키워드 자동 보충용 기본 니치 (대시보드 미설정 시 폴백)
DEFAULT_FALLBACK_NICHES = [
    "AI 활용 & 생산성", "재테크 & 투자", "부업 & 수익화",
    "정부지원 & 보조금", "세무 & 절세", "여행 & 라이프",
    "건강 & 웰니스", "뷰티 & 패션", "생활가전 & 스마트홈",
    "교육 & 자기계발", "행사 & 트렌드", "비교 & 리뷰",
]

# ── 단계별 수익화 설정 ──
STAGE_CONFIG = {
    1: {"adsense_mode": True,  "quality_min": 85, "kw_mix": {"traffic": 1.0, "conversion": 0.0, "high_cpa": 0.0}},
    2: {"adsense_mode": False, "quality_min": 80, "kw_mix": {"traffic": 0.7, "conversion": 0.2, "high_cpa": 0.1}},
    3: {"adsense_mode": False, "quality_min": 75, "kw_mix": {"traffic": 0.5, "conversion": 0.35, "high_cpa": 0.15}},
}

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

# ── 니치 그룹별 글쓰기 스타일 (톤 + 구조 + 비주얼 색상) ──
# 각 니치 slug → 그룹 ID 매핑
NICHE_GROUP_MAP = {
    # ── 12개 표준 니치 (워크플로우 드롭다운) ──
    "AI 활용 & 생산성": "product",
    "재테크 & 투자": "product",
    "부업 & 수익화": "promo",
    "정부지원 & 보조금": "info",
    "세무 & 절세": "info",
    "여행 & 라이프": "lifestyle",
    "건강 & 웰니스": "product",
    "뷰티 & 패션": "product",
    "생활가전 & 스마트홈": "product",
    "교육 & 자기계발": "product",
    "행사 & 트렌드": "info",
    "비교 & 리뷰": "product",
    # ── 레거시 slug 호환 ──
    "ai-tools": "product",
    "finance-invest": "product",
    "side-income": "promo",
    "tech-review": "product",
    "gov-support": "info",
    "tax-saving": "info",
    "insurance-finance": "product",
    "life-economy": "info",
    # ── 레거시 호환 ──
    "tech": "product", "smart-home": "product",
    "pet": "product", "appliance": "product", "beauty": "product",
    "health": "product", "baby": "product", "fitness": "product",
    "finance": "product", "education": "product",
    # 뉴스/리서치
    "news-sbs": "news", "news-kbs": "news", "news-jtbc": "news",
    "news-mbc": "news", "sns-trend": "news", "top10-corp": "news",
    # 섹터 리서치
    "s-semi": "sector", "s-ai": "sector", "s-defense": "sector",
    "s-pharma": "sector", "s-chem": "sector", "s-robot": "sector",
    "s-security": "sector", "s-enter": "sector", "s-ev": "sector",
    "s-space": "sector",
    # 정보 서비스
    "tax-guide": "info", "agency": "info",
    "event": "info", "travel": "info", "keyword-collect": "info",
    # 홍보/마케팅
    "niche-promo": "promo", "brand": "promo", "compare-land": "promo",
    # ── bomissu.com 생활경제 카테고리 (여성스러운 라이프스타일) ──
    "정부지원·복지": "lifestyle", "절세·세금": "lifestyle",
    "부업·수익화": "lifestyle", "보험·금융": "lifestyle",
    "생활비·살림": "lifestyle",
}

NICHE_STYLES = {
    "product": {
        "label": "제품 리뷰/비교",
        "tone": (
            "직접 써본 사람의 생생한 경험담 톤. "
            "'실제로 2주간 사용해보니' 같은 체험 기반 서술. "
            "스펙 나열보다 '그래서 내 생활이 어떻게 바뀌었는지'에 집중."
        ),
        "value_focus": "돈 아끼기(가성비/최저가) + 시간 절약(비교 대신 해줌) + 남들이 모르는 숨은 기능",
        "must_blocks": (
            "- 장단점 비교표 <table> 필수 (가격/성능/가성비 — 돈 아끼는 선택 도움)\n"
            "- <div class=\"tip-box\">: '이것만 확인하면 실패 없는 구매' (노력 절감)\n"
            "- <blockquote>: '대부분 모르는 숨은 기능/스펙' (남들이 모르는 정보)\n"
            "- <div class=\"key-point\">: '결론: 이 예산이면 이것, 저 예산이면 저것' (성과 향상)"
        ),
        "accent": "#6366f1",
        "accent_light": "#ede9fe",
        "accent_gradient": "linear-gradient(135deg,#6366f1,#818cf8)",
    },
    "news": {
        "label": "뉴스/리서치",
        "tone": (
            "속보 기자의 팩트 중심 톤. 두괄식 서술 (결론→근거→배경). "
            "감정 배제, 팩트와 수치로 승부. "
            "'왜 지금 이게 중요한지'를 첫 3줄에서 설명."
        ),
        "value_focus": "돈 버는 기회(시장 변화에서 기회 포착) + 시간 절약(핵심만 정리) + 남들이 모르는 배경",
        "must_blocks": (
            "- <blockquote>: 핵심 팩트 — '이 수치가 의미하는 것' (남들이 모르는 해석)\n"
            "- <div class=\"key-point\">: '30초 요약' — 바쁜 독자를 위한 핵심 (시간 절약)\n"
            "- <table>: 이해관계자별 영향 비교 — '나에게 어떤 영향?' (돈/시간 영향 분석)\n"
            "- <div class=\"tip-box\">: '이 뉴스로 돈 아끼는/버는 법' (실질 해석)"
        ),
        "accent": "#dc2626",
        "accent_light": "#fef2f2",
        "accent_gradient": "linear-gradient(135deg,#dc2626,#ef4444)",
    },
    "sector": {
        "label": "섹터 리서치",
        "tone": (
            "증권 애널리스트 리포트 톤. 데이터와 전망 중심. "
            "'수치로 보는 현황 → 전문가 분석 → 투자 시사점' 흐름. "
            "추측이 아닌 근거 기반 서술, 출처 명시."
        ),
        "value_focus": "돈 버는 정보(투자 시사점) + 성과 향상(더 나은 투자 판단) + 남들이 모르는 데이터",
        "must_blocks": (
            "- <table>: 핵심 수치 비교표 — 경쟁사/섹터/기간별 (성과 향상 판단 근거)\n"
            "- <blockquote>: '시장이 아직 반영 못한 사실' (남들이 모르는 정보 = 돈 버는 기회)\n"
            "- <div class=\"key-point\">: '투자 시사점: 지금 해야 할 것/하지 말아야 할 것' (성과 향상)\n"
            "- <div class=\"tip-box\">: '리스크 체크리스트 — 이것만 확인하세요' (노력 절감)"
        ),
        "accent": "#0891b2",
        "accent_light": "#ecfeff",
        "accent_gradient": "linear-gradient(135deg,#0891b2,#06b6d4)",
    },
    "info": {
        "label": "정보 서비스",
        "tone": (
            "친절한 공무원이 알려주는 톤. 복잡한 제도를 쉽게 풀어 설명. "
            "'누가, 언제, 어떻게 신청하는지' 단계별 가이드 중심. "
            "전문 용어는 반드시 괄호로 쉬운 설명 병기."
        ),
        "value_focus": "돈 아끼기(지원금/혜택) + 노력 절감(복잡한 절차 간소화) + 남들이 모르는 숨은 혜택",
        "must_blocks": (
            "- <table>: 자격 요건/지원 금액/신청 기간 정리표 (돈 아끼는 정보 한눈에)\n"
            "- <div class=\"tip-box\">: '90%가 놓치는 추가 혜택/서류' (남들이 모르는 것)\n"
            "- <div class=\"key-point\">: '나도 대상자? 3가지만 확인하세요' (노력 절감)\n"
            "- <blockquote>: '이것 때문에 탈락하는 사람이 많습니다' (시간+돈 절약)"
        ),
        "accent": "#059669",
        "accent_light": "#ecfdf5",
        "accent_gradient": "linear-gradient(135deg,#059669,#10b981)",
    },
    "promo": {
        "label": "홍보/마케팅",
        "tone": (
            "브랜드 스토리텔러 톤. '문제 상황 → 해결 과정 → 변화된 결과' 내러티브. "
            "감성적 공감과 사회적 증거(후기, 수치) 조화. "
            "직접적 판매 권유 대신 '왜 이것이 가치 있는지' 설득."
        ),
        "value_focus": "성과 향상(Before→After 변화) + 시간 절약(직접 찾아보지 않아도 됨) + 돈 아끼기(할인/프로모션)",
        "must_blocks": (
            "- <blockquote>: 실사용자 Before→After 변화 수치 (성과 향상 증거)\n"
            "- <div class=\"tip-box\">: '오늘 시작하는 가장 쉬운 방법' (노력 절감)\n"
            "- <table>: 경쟁 대안 비교표 — 가격/기능/만족도 (돈 아끼는 선택)\n"
            "- <div class=\"key-point\">: '이 글의 핵심: 왜 지금인가' (시간 절약)"
        ),
        "accent": "#d946ef",
        "accent_light": "#fdf4ff",
        "accent_gradient": "linear-gradient(135deg,#d946ef,#e879f9)",
    },
    "lifestyle": {
        "label": "생활경제 라이프스타일",
        "tone": (
            "친한 언니/오빠가 알려주는 톤. 부드럽고 따뜻하지만 정확한 정보. "
            "'이건 내가 직접 해봤는데' 같은 경험 기반 서술. "
            "어려운 용어는 쉽게 풀어주고, 실질적으로 돈 아끼는 방법에 집중."
        ),
        "value_focus": "돈 아끼기(지원금/절세/할인) + 노력 절감(복잡한 절차 쉽게) + 시간 절약(핵심만 정리)",
        "must_blocks": (
            "- <table>: 자격 요건/금액/기간 비교표 — 한눈에 보는 정리 (돈 아끼는 선택)\n"
            "- <div class=\"tip-box\">: '대부분 모르는 추가 혜택/꿀팁' (남들이 모르는 정보)\n"
            "- <div class=\"key-point\">: '핵심 요약: 이것만 기억하세요' (노력 절감)\n"
            "- <blockquote>: '놓치면 손해! 꼭 확인하세요' (긴급성+실용성)"
        ),
        "accent": "#E8796B",
        "accent_light": "#FFF0ED",
        "accent_gradient": "linear-gradient(135deg,#E8796B,#F4A89A)",
    },
}

def get_niche_style(category):
    """카테고리(니치 slug)에 해당하는 스타일 반환. 없으면 product 기본값."""
    group = NICHE_GROUP_MAP.get(category, "product")
    return NICHE_STYLES.get(group, NICHE_STYLES["product"]), group


# 니치별 도메인 키워드 (AI가 조합에 사용)
NICHE_DOMAINS = {
    # === 12개 표준 니치 (워크플로우 드롭다운과 동일) ===
    "AI 활용 & 생산성": ["ChatGPT", "Claude", "Gemini", "Midjourney", "Cursor", "NotebookLM", "Perplexity", "Copilot", "Suno", "Gamma", "Descript", "Runway", "노션", "구글워크스페이스"],
    "재테크 & 투자": ["적금", "ETF", "주식", "대출", "보험", "연금", "절세", "부동산", "배당주", "ISA", "IRP", "비트코인", "금투자"],
    "부업 & 수익화": ["블로그수익화", "쿠팡파트너스", "스마트스토어", "애드센스", "유튜브", "크몽", "전자책", "디지털노마드", "N잡러", "워드프레스"],
    "정부지원 & 보조금": ["정부보조금", "청년정책", "소상공인지원", "창업지원", "고용보험", "육아수당", "주거지원", "실업급여", "국민취업지원", "기초연금", "전기차보조금"],
    "세무 & 절세": ["종합소득세", "부가세", "연말정산", "세금환급", "절세전략", "부양가족공제", "의료비공제", "월세세액공제", "간이과세자", "경비처리"],
    "여행 & 라이프": ["항공권", "호텔", "패키지", "자유여행", "제주도", "일본여행", "전월세", "생활비절약", "호캉스", "캠핑"],
    "건강 & 웰니스": ["영양제", "다이어트", "운동루틴", "수면", "스트레스관리", "건강검진", "유산균", "단백질보충제", "홈트레이닝", "눈건강"],
    "뷰티 & 패션": ["스킨케어", "선크림", "파운데이션", "헤어케어", "뷰티디바이스", "성분분석", "그루밍", "탈모예방", "계절코디"],
    "생활가전 & 스마트홈": ["노트북", "태블릿", "무선이어폰", "공기청정기", "로봇청소기", "스마트스피커", "모니터", "에어컨", "스마트도어락", "NAS"],
    "교육 & 자기계발": ["온라인강의", "자격증", "영어독학", "코딩교육", "독서법", "생산성앱", "시간관리", "자기계발", "AI역량"],
    "행사 & 트렌드": ["CES", "MWC", "애플이벤트", "갤럭시언팩", "IT트렌드", "경제전망", "AI반도체", "컨퍼런스"],
    "비교 & 리뷰": ["가격비교", "스펙비교", "장단점분석", "보험비교", "요금제비교", "OTT비교", "전기차비교", "정수기비교"],
    # === 레거시 호환 ===
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
    "gov-support": ["정부보조금", "청년정책", "소상공인지원", "창업지원", "고용보험", "육아수당", "주거지원", "긴급생활지원", "국민취업지원", "기초연금"],
    "tax-saving": ["종합소득세", "부가세", "연말정산", "세금환급", "절세전략", "부양가족공제", "의료비공제", "월세세액공제", "사업소득세", "종소세신고", "세금계산기", "원천징수"],
    "insurance-finance": ["실손보험", "자동차보험", "건강보험", "암보험", "종신보험", "보험비교", "보험리모델링", "대출금리비교", "신용대출", "전세대출", "주택담보대출", "적금추천"],
    "life-economy": ["생활비절약", "교통비할인", "통신비절감", "공과금절약", "카드혜택", "포인트활용", "알뜰소비", "구독절약", "중고거래", "재테크기초", "가계부", "짠테크"],
    "side-income": ["블로그수익화", "쿠팡파트너스", "스마트스토어", "애드센스", "재능판매", "배달부업", "투잡", "디지털노마드", "N잡러", "크몽프리랜서", "중고거래수익", "부업추천"],
    "finance-invest": ["적금추천", "예금금리비교", "주식입문", "ETF투자", "연금저축", "IRP", "ISA계좌", "보험비교", "실손보험", "자동차보험", "건강보험", "대출금리"],
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

    def __init__(self, site_niches=None):
        self.site_niches = site_niches or []  # 키워드 파일에서 가져온 사이트별 니치
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

    def generate(self, count=5, fallback=False):
        """선택된 니치에서 다양한 키워드 동적 생성
        fallback=True: 정적 키워드 소진 시 호출. autoMode/니치 설정 무시하고 기본 니치로 생성.
        """
        # autoMode 체크 (폴백 모드에서는 스킵 — 키워드 없으면 무조건 생성해야 함)
        if not fallback and SUPABASE_URL and SUPABASE_KEY:
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
            if fallback:
                # 우선순위: 사이트 키워드 파일 니치 → 글로벌 기본 니치
                if self.site_niches:
                    niches = list(self.site_niches)
                    log.info(f"  키워드 자동 보충 — 사이트 니치 사용: {niches}")
                else:
                    niches = list(DEFAULT_FALLBACK_NICHES)
                    log.info(f"  키워드 자동 보충 — 기본 니치 폴백: {niches}")
                random.shuffle(niches)
                niches = niches[:3]
            else:
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

        # 1순위: Gemini (무료) — 모델 폴백: 2.0-flash → 2.0-flash-lite → 1.5-flash
        if GEMINI_KEY:
            for _model in ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]:
                try:
                    resp = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent?key={GEMINI_KEY}",
                        headers={"Content-Type": "application/json"},
                        json={"contents": [{"parts": [{"text": prompt}]}],
                              "generationConfig": {"temperature": 1.0, "maxOutputTokens": 2000}},
                        timeout=30
                    )
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    continue

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
DRAFT_PROMPT_KO = """당신은 이 분야를 직접 경험하고 연구한 전문가이며, 동시에 독자의 감정을 움직이는 스토리텔러입니다.

키워드: {keyword}
검색의도: {intent}
카테고리: {category}

=== 독자가 진짜 원하는 6가지 가치 (핵심 프레임워크) ===
모든 문단은 아래 6가지 중 최소 1가지를 독자에게 제공해야 합니다:
1. 돈 버는 정보: 수익을 만드는 구체적 방법/기회/루트
2. 돈 아끼는 정보: 할인, 무료 대안, 숨겨진 혜택, 불필요한 지출 차단법
3. 시간 절약: 빠른 방법, 자동화, 핵심만 정리, "이것만 하면 된다"
4. 노력 절감: 쉬운 대안, 템플릿, 복사해서 쓸 수 있는 것, 단계 축소
5. 성과 향상: 같은 노력으로 더 나은 결과를 내는 전략/도구/팁
6. 남들이 모르는 것: 업계 인사이더 정보, 숨겨진 기능, 잘 안 알려진 혜택

글을 읽는 독자가 "이 글에서 진짜 쓸모 있는 걸 얻었다"고 느껴야 합니다.
빈 주장, 일반론, 누구나 아는 상식은 가치가 없습니다.

=== 글의 감정 설계 (시나리오 아크) ===
이 글은 독자의 감정을 다음 흐름으로 이끌어야 합니다:
1단계 [감정 훅] 공감 → 2단계 [호기심] "이런 게 있었어?" → 3단계 [신뢰+도파민] 놀라운 수치/사실 → 4단계 [행동 욕구] "나도 해봐야지"

=== 구조 규칙 ===
1. 제목: <title> 태그. 독자가 "이건 꼭 읽어야 해"라고 느끼는 제목
   - 숫자/구체적 혜택/긴급성 중 1개 이상 포함
   - SEO: 키워드를 제목 앞부분에 자연스럽게 배치
   - 제목에 코드, 해시값, 영문 ID 등 기술적 문자열 절대 포함 금지

2. 도입부 (감정 훅): 3~4문장
   - 첫 문장: 독자의 고민/상황을 콕 찔러 감정 이입 유도
   - 둘째 문장: "사실 대부분은 이걸 모르고 있어요" 식의 호기심 점화
   - 마지막: 이 글을 읽으면 얻을 구체적 가치를 약속 (6가지 중 어떤 가치인지 명시)

3. 본문: H2 소제목 5~7개, 각 300~500자
   - 키워드를 H2 2~3개에 자연스럽게 포함 (SEO)
   - 모든 주장에 구체적 수치/비교/출처 (근거 없는 문장 금지)
   - 각 섹션의 첫 문장에서 "이 섹션을 읽으면 얻는 가치"를 암시
   - <strong> 핵심 정보 강조 (최소 7개)

4. 가치 블록 (본문 전체에 걸쳐 필수 삽입):
   - <blockquote>: 남들이 모르는 놀라운 사실/수치 (도파민 트리거)
   - <div class="tip-box">: 바로 실행하면 시간/돈/노력을 절약하는 구체적 팁
   - <div class="key-point">: 이 섹션에서 당장 써먹을 수 있는 핵심 1줄 요약
     주의: key-point 안에 ①②③ 번호가 있으면 각 번호마다 줄바꿈하여 깔끔하게 정리
   - <table>: 비교해서 최적의 선택을 돕는 표 (<thead>+<tbody> 필수)
   위 4종 블록을 글 전체에 각 1~2개씩 (같은 블록 연속 배치 금지)

5. 관련 사이트/링크: 주제와 관련된 공식 사이트나 유용한 리소스가 있다면 본문에 자연스럽게 포함
   - 예: "자세한 내용은 <a href='https://k-startup.go.kr' target='_blank'>K-Startup 포털</a>에서 확인하세요"
   - 정부 사이트, 공식 도구 페이지, 공인 기관 링크만 (개인 블로그/광고 링크 금지)

6. 마무리: "이 글에서 얻은 것" 핵심 3줄 + 구체적 다음 행동 1가지

6. 톤: 한국 독자 맞춤 — 쉽고 친근하게
   - 옆집 형/누나가 알려주듯 편안한 말투 ("~해요", "~거든요", "~이에요")
   - "~입니다", "~한 것입니다" 같은 딱딱한 문체 금지
   - 번역체/영어식 표현 절대 금지 ("레버리지", "인사이더 정보", "스케일링" → 한국어로 풀어쓰기)
   - 전문 용어는 반드시 괄호로 쉽게 풀이: "엣지AI(내 기기에서 직접 돌리는 AI)"
   - 중학생도 이해할 수 있는 수준으로 쓰기 — 어려운 개념은 비유로 먼저 설명
   - 짧은 문장(5어절)과 긴 문장(15어절) 리듬감 있게 교차

7. 나열/목록 규칙:
   - 3개 이상 항목을 나열할 때는 반드시 <ol> 또는 <ul>로 줄바꿈 정리
   - 한 문장에 1, 2, 3, 4 쭉 나열 금지 — 각 항목을 <li>로 분리
   - 각 <li>는 1~2문장으로 간결하게

8. 분량: 4,000~6,000자 (군더더기 없이 핵심만)
   - 글자수 맞추기 위한 불필요한 서론/반복/장황한 설명 금지
   - 모든 문장이 독자에게 가치를 줘야 함 — 안 주는 문장은 삭제

9. E-E-A-T 시그널 (구글 SEO 핵심):
   - Experience(경험): "직접 해보니", "실제로 신청해봤는데" 등 1인칭 경험 서술 1~2회
   - Expertise(전문성): 정확한 수치, 공식 출처, 근거법령/제도명 명시
   - Authoritativeness(권위): 정부 사이트, 공식 기관, 신뢰할 수 있는 통계 인용
   - Trustworthiness(신뢰): "2026년 4월 기준", "2025년 개정 기준" 등 최신 시점 명시
   - 도입부에 "이 글의 핵심 내용" 요약 (검색 결과 Featured Snippet 최적화)

10. 내부 링크 유도 문구:
    - 본문 중간 1~2회 "관련 글: OO에 대해 더 알아보기" 식의 앵커 유도 (실제 링크 없이 텍스트만)
    - 마무리에서 "다음에 읽으면 좋은 주제: OO" 제안

=== HTML 규칙 (절대 준수) ===
- <title>글제목</title>을 최상단에
- <h2>, <p>, <strong>, <ul>/<ol>, <table>, <blockquote> 사용
- <div class="tip-box">, <div class="key-point"> 사용 가능
- <h1> 금지 (워드프레스 자동 생성)
- 각 <p>는 2~4문장, H2 사이 최소 2개 <p>
- <table>은 반드시 <thead><tr><th>헤더</th></tr></thead><tbody><tr><td>내용</td></tr></tbody> 구조
- 마크다운 문법 절대 금지: **bold**, *italic*, ```code```, ## 제목, – 대시 리스트 사용 금지
- 굵게: <strong>, 목록: <ol><li> 또는 <ul><li>
- 연속으로 같은 블록(tip-box, key-point, blockquote) 2개 배치 금지
"""

POLISH_PROMPT_KO = """아래 블로그 초안을 독자가 즐겨찾기에 저장할 수준으로 업그레이드하세요.

키워드: {keyword}

=== 가치 검증 (최우선) ===
초안의 모든 문단을 아래 6가지 가치 기준으로 점검하세요:
- 돈 버는 정보 / 돈 아끼는 정보 / 시간 절약 / 노력 절감 / 성과 향상 / 남들이 모르는 것
각 문단이 6가지 중 하나도 제공하지 않으면 → 구체적 수치/팁/방법으로 보강하거나 삭제
"일반론", "~가 중요합니다", "~를 고려해야 합니다" 같은 빈 문장은 100% 제거

=== 업그레이드 규칙 ===
1. AI 특유 표현 + 번역체 완전 제거:
   - AI 표현: "다양한", "중요합니다", "살펴보겠습니다", "관심이 높아지고 있습니다"
   - 번역체: "레버리지하다", "인사이더 정보", "스케일링", "파이프라인", "워크플로우"
   → 한국어 자연어로 100% 교체 (예: "스케일링" → "규모 키우기", "워크플로우" → "작업 흐름")
2. 난이도 점검: 중학생도 이해할 수 있는지 확인
   - 전문 용어에 괄호 풀이가 없으면 추가
   - 어려운 개념은 비유를 먼저 넣기
3. 모든 문단에 구체적 수치/사례/비교 1개 이상 (빈 주장 금지)
4. 문장 리듬: 짧은 문장(5어절)과 긴 문장(15어절) 교차
5. 감정 설계: 도입부에 감정 훅 → 본문에서 호기심+놀라움 → 마무리에서 행동 욕구
6. 키워드를 H2 2~3개, 도입부, 마무리에 자연스럽게 배치 (SEO)
7. 가치 블록 확인: <blockquote> 1개+, <div class="tip-box"> 1개+, <div class="key-point"> 1개+ 없으면 추가
8. 나열 점검: 3개+ 항목이 한 문장에 나열되어 있으면 <ol>/<ul>로 분리
9. <strong> 최소 7개 이상
10. 군더더기 제거: 글자수 채우기용 반복/장황한 설명 삭제. 4,000~6,000자면 충분
11. HTML 구조 유지. 마크다운 잔재(**bold**, ```code```) 발견 시 HTML로 교체
12. <table>이 있으면 반드시 <thead><tr><th>...</th></tr></thead><tbody>... 구조
13. E-E-A-T 점검:
    - 1인칭 경험 서술이 1~2회 있는지 (없으면 자연스럽게 추가)
    - 수치/통계에 시점("2026년 기준")이 명시되어 있는지
    - 도입부에 "이 글의 핵심" 요약이 있는지 (Featured Snippet 최적화)
    - 공식 사이트/기관 이름이 1개 이상 언급되어 있는지

=== 절대 금지 (출력 형식) ===
- 폴리싱된 HTML 본문만 출력하세요. 그 외 아무것도 출력하지 마세요.
- "수정 내역", "폴리싱 요약", "변경 사항", "수정한 부분" 등 메타 설명 금지
- 인사말, 서문, 맺음말 등 부가 텍스트 금지
- <title>로 시작해서 HTML 본문으로 끝나야 합니다

초안:
{draft}
"""

# ── 영문 프롬프트 (Consumer-first) ──
DRAFT_PROMPT_EN = """You are a hands-on expert who has personally researched and tested everything in this topic.
Write for a reader who Googled this problem and needs a real, actionable answer.

Keyword: {keyword}
Search Intent: {intent}
Category: {category}

=== Core Principle: Reader Value First ===
1. Title: Address the reader's actual problem. Wrap in <title> tag.
   - Make the reader think "This will solve my problem"
   - NEVER include codes, hashes, or technical IDs in the title
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

=== OUTPUT FORMAT (CRITICAL) ===
- Output ONLY the polished HTML content. Nothing else.
- Do NOT include "Changes made:", "Summary:", "Revision notes:" or any meta-commentary.
- Start with <title> and end with the HTML body. No greetings or explanations.

Draft:
{draft}
"""

# ── AdSense 승인 전용 프롬프트 (한국어) ──
ADSENSE_DRAFT_PROMPT_KO = """당신은 이 분야의 권위 있는 전문가이며, 독자의 감정을 설계하는 스토리텔러입니다.
독자가 즐겨찾기에 저장하고 주변에 공유할 만큼 완벽한 레퍼런스 글을 작성합니다.

키워드: {keyword}
검색의도: {intent}
카테고리: {category}

=== 독자가 진짜 원하는 6가지 가치 (핵심 프레임워크) ===
모든 문단은 아래 6가지 중 최소 1가지를 독자에게 제공해야 합니다:
1. 돈 버는 정보: 수익을 만드는 구체적 방법/기회/루트
2. 돈 아끼는 정보: 할인, 무료 대안, 숨겨진 혜택, 불필요한 지출 차단법
3. 시간 절약: 빠른 방법, 자동화, 핵심만 정리, "이것만 하면 된다"
4. 노력 절감: 쉬운 대안, 템플릿, 복사해서 쓸 수 있는 것, 단계 축소
5. 성과 향상: 같은 노력으로 더 나은 결과를 내는 전략/도구/팁
6. 남들이 모르는 것: 업계 인사이더 정보, 숨겨진 기능, 잘 안 알려진 혜택

빈 주장, 일반론, 누구나 아는 상식은 가치가 없습니다. 독자가 "이건 진짜 유용하다"고 느끼는 정보만 담으세요.

=== 글의 감정 설계 (시나리오 아크) ===
1단계 [감정 훅] 공감 → 2단계 [호기심] "이런 게 있었어?" → 3단계 [신뢰+도파민] 놀라운 수치/사실 → 4단계 [행동 욕구] "나도 해봐야지"

=== GEO (AI 검색 인용) + AdSense 승인 + SEO 최적화 품질 기준 ===
[GEO 필수 구조 — ChatGPT·Perplexity·Google AI Overview·Naver AI가 인용하는 글 패턴]
0. TL;DR 박스 (글 최상단, <title> 바로 아래):
   - <div class="tldr-box"><strong>핵심 요약:</strong> [키워드]에 대한 직접 답변을 3줄 이내로</div>
   - 첫 100자 안에 키워드에 대한 직접 답변 포함 (AI가 이 구간을 가장 많이 인용)
   - 예시: "ETF 투자는 최소 1주(약 5천원~)부터 가능하며, KODEX·TIGER 등 국내 ETF로 분산투자가 가능합니다."
1. 제목: <title> 태그. 키워드를 앞부분에 자연스럽게 포함. 전문적+검색 친화적
   - 독자에게 제공하는 가치가 제목에 드러나야 함 (절약/비법/방법/비교 등)
   - 제목에 코드, 해시값, 영문 ID 등 기술적 문자열 절대 포함 금지
2. 도입부 (감정 훅 + GEO 직접 답변): 4~5문장
   - 첫 문장에서 독자의 상황/고민을 정확히 공감
   - 두 번째 문장에 키워드에 대한 직접 답변 1줄 포함 (AI 스니펫 최적화)
   - "사실 대부분은 이걸 놓치고 있어요" 식의 호기심 점화
   - 이 글을 읽으면 얻는 구체적 가치를 약속 (6가지 가치 중 어떤 것인지 명시)
3. 본문: H2 소제목 7~9개, 각 400~600자
   - H2는 반드시 독자 질문 형태로 작성 (AI 인용 최적화): "~은 어떻게 하나요?", "~의 차이는 무엇인가요?", "~하면 안 되는 이유는?"
   - 각 H2 바로 아래 첫 문장 = 해당 질문에 대한 직접 답변 (2~3문장, AI가 발췌하는 구간)
   - 모든 수치/데이터는 출처 명시: "2025년 기준 (출처: KRX/네이버금융/통계청)"
   - 키워드를 H2 3~4개에 자연스럽게 포함 (SEO)
   - 모든 주장에 데이터/통계/전문가 의견 (E-E-A-T)
   - 각 섹션에서 독자가 당장 써먹을 수 있는 액션 아이템 1개 이상
   - <strong> 강조 최소 10개
   - 외부 광고성 링크 절대 금지
4. 가치 블록 (본문 전체에 각 1~2개씩, 같은 블록 연속 금지):
   - <blockquote>: 남들이 모르는 놀라운 사실/수치 (도파민 트리거)
   - <div class="tip-box">: 바로 실행하면 돈/시간/노력을 절약하는 구체적 팁
   - <div class="key-point">: 이 섹션 핵심 1줄 (①②③ 번호 있으면 각각 줄바꿈 정리)
   - <table>: 비교해서 최적의 선택을 돕는 표 (<thead>+<tbody> 필수)
5. 관련 사이트 링크: 공식 사이트/도구가 있으면 <a href="URL" target="_blank">사이트명</a>으로 안내
   - 정부 포털, 공식 도구, 공인 기관만 (광고 링크 금지)
6. 마무리: "이 글에서 얻은 것" 핵심 3~5줄 + FAQ 5개 (GEO 강화)
   - FAQ는 실제 사람들이 AI에게 물어볼 법한 구체적 질문으로 구성
   - 형식: <div class="faq-section"><h3>Q. [질문]</h3><p><strong>A.</strong> [2~3문장 직접 답변. 수치/사실 포함]</p></div>
   - FAQ 뒤에 JSON-LD Schema 삽입 (Perplexity·Google AI 파싱용):
     <script type="application/ld+json">{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[{"@type":"Question","name":"[질문1]","acceptedAnswer":{"@type":"Answer","text":"[답변1]"}},{"@type":"Question","name":"[질문2]","acceptedAnswer":{"@type":"Answer","text":"[답변2]"}}]}</script>
7. 톤: 한국 독자 맞춤 — 신뢰감 있으면서 쉽고 친근하게
   - 옆집 형/누나가 알려주듯 편안한 말투 ("~해요", "~거든요")
   - 번역체/영어식 표현 절대 금지 → 한국어로 풀어쓰기
   - 전문 용어는 괄호로 쉽게 풀이: "ETF(여러 주식을 한 바구니에 담은 상품)"
   - 중학생도 이해할 수 있는 수준 — 어려운 개념은 비유로 먼저
   - 질문→답변, 문제→해결 패턴
   - 짧은 문장과 긴 문장 리듬감 있게 교차
7. 나열/목록: 3개 이상 항목은 반드시 <ol>/<ul>로 줄바꿈 정리. 한 문장에 나열 금지.
8. 분량: 5,000~7,000자 (군더더기 없이 알차게)
   - 글자수 채우기 위한 반복/장황한 서론 금지
9. 품질: 이 글 하나로 해당 주제의 모든 궁금증이 해결되는 수준

=== AdSense 승인 안전 가이드라인 (필수 준수) ===
아래 주제/표현은 AdSense 정책 위반으로 승인 거부됩니다. 절대 포함 금지:
- 도박, 카지노, 베팅, 스포츠 토토 관련 내용
- 성인, 선정적, 데이팅 앱 관련 내용
- 주류, 담배, 마약, 약물 관련 내용
- 무기, 폭력, 잔인한 묘사
- 저작권 침해 콘텐츠 (타 사이트 글 복사/번역)
- 의료 진단/처방 (전문의 상담을 대체하는 내용)
- 허위/과장 수익 약속 ("월 1000만원 보장", "100% 수익" 등)
- 불법 다운로드, 해킹, 크랙 관련 내용
- 정치적 편향, 혐오 발언, 차별적 표현
콘텐츠는 반드시 정보성·교육적·유용한 내용이어야 합니다.

=== HTML 규칙 (절대 준수) ===
- <title>글제목</title>을 최상단에
- <h2>, <h3>, <p>, <strong>, <ul>/<ol>, <table>, <blockquote> 사용
- <div class="tip-box">, <div class="key-point"> 사용 가능
- <h1> 금지
- 각 <p>는 2~3문장, H2 사이 최소 3개 <p>
- <table>은 반드시 <thead><tr><th>헤더</th></tr></thead><tbody><tr><td>내용</td></tr></tbody> 구조
- FAQ는 <h3>질문</h3><p>답변</p> 형식
- 마크다운 문법 절대 금지: **bold**, *italic*, ```code```, ## 제목, – 대시 리스트 사용 금지
- 굵게: <strong>, 목록: <ol><li> 또는 <ul><li>
- 연속으로 같은 블록(tip-box, key-point, blockquote) 2개 배치 금지
"""

# ── AdSense 승인 전용 프롬프트 (영문) ──
ADSENSE_DRAFT_PROMPT_EN = """You are an authoritative expert in this field.
Write a definitive reference article that readers will bookmark and share.

Keyword: {keyword}
Search Intent: {intent}
Category: {category}

=== AdSense Approval Quality Standards ===
1. Title: Professional and search-friendly. Wrap in <title> tag.
   - NEVER include codes, hashes, or technical IDs in the title
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

# ═══════════════════════════════════════════════════════
# Golden Mode 전용 프롬프트 — Gemini 피드백 3대 전략 반영
# 1) 페르소나 주입 (15년차 전문가 Insider)
# 2) 독점적 프레임워크 네이밍 ([영문3자리] + [법칙/매트릭스/시스템])
# 3) 데이터 앵커링 (서론 3초 만에 수치 기반 권위 확보)
# ═══════════════════════════════════════════════════════

# 도입부 패턴 12종 — 매 글마다 랜덤 선택 (패턴 분석 방지)
GOLDEN_INTRO_HOOKS = [
    # 1. 역설 훅 — 통념 뒤집기
    """도입부 패턴: [역설 훅]
"대부분의 사람들이 ~라고 믿고 있지만, 실제 데이터는 정반대를 가리킵니다."
→ 독자가 '상식'이라고 믿던 것을 구체적 수치로 뒤집으며 시작. 충격과 호기심을 동시에 유발.
첫 문장에서 통념을 제시하고, 두 번째 문장에서 데이터로 즉시 반박하십시오.""",

    # 2. 수치 폭탄 — 놀라운 통계 직격
    """도입부 패턴: [수치 폭탄]
첫 문장을 반드시 충격적인 숫자/통계로 시작하십시오. 예: "국내 ~시장 규모가 130조 원을 돌파했습니다."
→ 수치 자체가 훅이 됩니다. 독자는 '이 정도인 줄 몰랐다'는 반응과 함께 글을 계속 읽습니다.
세 번째 문장에서 "그런데 이 시장에서 실제로 수익을 내는 비율은 ~%에 불과합니다"로 긴장감을 추가.""",

    # 3. 시간 대비 — 과거 vs 현재
    """도입부 패턴: [시간 대비]
"2년 전만 해도 ~였습니다. 그러나 지금은 완전히 다른 판이 열렸습니다."
→ 과거와 현재의 극적인 변화를 대비시켜 '지금 알아야 할 이유'를 만듭니다.
반드시 과거 수치와 현재 수치를 병렬 제시하여 변화의 크기를 체감시키십시오.""",

    # 4. 실패 시나리오 — 손실 회피 심리
    """도입부 패턴: [실패 시나리오]
"이 글을 읽지 않고 ~를 시작한다면, 통계적으로 73%의 확률로 ~한 결과를 맞이합니다."
→ 손실 회피 심리(Loss Aversion)를 자극합니다. 독자는 '실패하고 싶지 않다'는 본능으로 글을 끝까지 읽습니다.
실패의 구체적 비용(시간/돈/기회비용)을 수치로 제시하십시오.""",

    # 5. 질문 연타 — 3연속 공감 질문
    """도입부 패턴: [질문 연타]
3개의 연속 질문으로 시작하십시오. 각 질문은 독자의 현재 상황을 정확히 묘사해야 합니다.
예: "매달 ~만 원을 넣고 있지만 수익률은 제자리입니까? ~를 해봤지만 결과가 없었습니까? 정보는 넘치는데 뭘 해야 할지 더 모르겠습니까?"
→ 세 번째 질문 직후, "이 3가지 질문에 하나라도 해당된다면, 지금부터 제시하는 시스템이 답입니다."로 전환.""",

    # 6. 결론 선행 — 핵심 먼저
    """도입부 패턴: [결론 선행]
"결론부터 말씀드리겠습니다. ~하는 가장 효과적인 방법은 [프레임워크 이름]입니다."
→ 바쁜 독자의 시간을 존중하는 전문가적 어프로치. 결론을 먼저 던지고, '왜 이것이 최선인지' 데이터로 증명하는 구조.
두 번째 문장에서 이 결론을 뒷받침하는 핵심 수치 1개를 즉시 제시하십시오.""",

    # 7. 뉴스/트렌드 앵커 — 최신 사건 연결
    """도입부 패턴: [뉴스 앵커]
"2026년 ~월, [관련 기관/시장]에서 ~가 발표되었습니다. 이 변화가 의미하는 것은 단 하나입니다."
→ 최신 트렌드/정책/시장 변화를 앵커로 삼아 글의 시의성을 확보합니다.
뉴스 팩트 → 독자에게 미치는 영향 → 이 글에서 제시할 해법, 3단계로 전개.""",

    # 8. 비유 도입 — 복잡한 개념을 일상으로
    """도입부 패턴: [비유 도입]
일상의 비유로 시작하되, 즉시 전문적 분석으로 전환하십시오.
예: "~는 마치 [일상 비유]와 같습니다. 그러나 대부분은 [비유의 핵심 원리]를 무시한 채 ~하고 있습니다."
→ 비유는 1~2문장으로 끝내고, 세 번째 문장부터 데이터와 수치로 전문가 모드 진입.""",

    # 9. 경고문 — 긴급성 부여
    """도입부 패턴: [경고문]
"지금 ~하고 계시다면, 즉시 멈추십시오."
→ 강한 경고로 시작하여 주의를 집중시킵니다. 두 번째 문장에서 '왜 멈춰야 하는지' 데이터로 근거 제시.
세 번째 문장에서 "대신 ~하는 것이 [수치]% 더 효과적입니다"로 대안 제시.""",

    # 10. 격차 제시 — 상위 vs 하위
    """도입부 패턴: [격차 제시]
"상위 5%는 ~하고, 나머지 95%는 ~합니다. 이 차이를 만드는 것은 단 하나의 시스템입니다."
→ 엘리트와 대중의 격차를 수치로 보여주어 '나도 상위로 가고 싶다'는 욕구를 자극합니다.
반드시 구체적 수치로 격차를 제시하고, 그 격차의 원인이 이 글의 주제임을 명시.""",

    # 11. 비용 계산 — 기회비용 환산
    """도입부 패턴: [비용 계산]
"~를 모르고 지나치면, 연간 약 ~만 원의 기회비용이 발생합니다."
→ 독자가 '안 읽으면 손해'라는 확신을 갖게 만듭니다. 기회비용을 연/월/일 단위로 환산하여 체감시키십시오.
두 번째 문장에서 "반대로, 이 시스템을 적용하면 ~의 효과를 기대할 수 있습니다"로 긍정 전환.""",

    # 12. 체크리스트 진단 — 자가 테스트
    """도입부 패턴: [체크리스트 진단]
"아래 3가지 중 2개 이상 해당된다면, 이 글은 반드시 읽어야 합니다."
→ 짧은 자가 진단 체크리스트(3~4항목)를 제시합니다. 독자가 자신의 상태를 점검하며 몰입합니다.
체크리스트 직후 "해당 항목이 많을수록, 지금부터 제시하는 [프레임워크]의 효과는 극대화됩니다."로 연결.""",
]

GOLDEN_DRAFT_PROMPT_KO = """# Role (역할)
당신은 상위 1%의 정보력과 냉철한 분석력을 갖춘 15년 차 산업/금융/비즈니스 전문가입니다.
당신의 목표는 레드오션에 널린 뻔한 정보가 아닌, 독자가 당장 실행할 수 있는 '시스템적 해결책'과 '압도적인 인사이트'를 제공하는 블로그 포스팅을 작성하는 것입니다.

# Core Topic
키워드: {keyword}
검색의도: {intent}
카테고리: {category}

# Constraint (작성 제약 조건 — 반드시 준수)
1. '제 지인', '제가 해봤는데' 같은 가벼운 경험담이나 감성적인 위로는 절대 배제할 것.
2. 대신, 논리적이고 객관적인 데이터(수치, 확률, 통계, 비교표)를 활용하여 모든 주장을 뒷받침할 것.
3. **독점적 프레임워크 네이밍 필수**: 이 글의 핵심 솔루션에 당신만의 독창적인 프레임워크 이름을 반드시 부여할 것.
   네이밍 규칙: [영문 알파벳 3자리 약자] + [직관적 명사] 형태
   예시: V.I.P 스노우볼, R.O.I 매트릭스, T.A.P 법칙, S.M.P 시스템
   본문 내내 이 명칭을 반복하여 권위성을 확보할 것.
4. **데이터 앵커링 필수**: 도입부 첫 3문장 안에 구체적인 수치/통계/확률을 배치하여 전문가로서의 권위를 즉시 확보할 것.
   예시: "국내 ETF 시장 규모가 2026년 기준 130조 원을 돌파하며..." / "평균 실패율 73%인 이 방법 대신..."
5. 문체는 단호하고 확신에 찬 전문가의 어조를 사용할 것 (~합니다, ~하십시오).
   단, 전문 용어는 반드시 괄호로 쉬운 설명 병기: "MDD(최대 낙폭, 투자 기간 중 최대 손실폭)"
6. 번역체/영어식 표현 절대 금지 → 한국어로 풀어쓰기
   ("레버리지" → "지렛대 효과", "스케일링" → "규모 확장", "포트폴리오" → "투자 바구니" 또는 괄호 병기)
7. 3개 이상 항목 나열 시 반드시 <ol> 또는 <ul>로 줄바꿈 정리. 한 문장에 나열 금지.
8. **할루시네이션 절대 금지 (CRITICAL)**:
   - 존재하지 않는 통계, 연구 결과, 기관명, 보고서를 절대 날조하지 말 것.
   - "~에 따르면", "~연구 결과" 등 인용 시 반드시 실존하는 출처만 사용할 것.
   - 정확한 출처를 모르면 "일반적으로 알려진 바에 따르면", "업계 전문가들의 분석에 의하면" 형태로 작성.
   - 구체적 수치 인용은 API 페이로드로 주입된 데이터 또는 널리 알려진 공개 통계만 허용.
   - 가짜 퍼센트(%), 가짜 금액, 가짜 기관명을 지어내는 것은 사이트 신뢰도를 파괴하는 행위임.
9. **수치 사용 규칙**:
   - 도입부 데이터 앵커링 수치는 해당 키워드/산업의 공개된 통계만 사용.
   - 정확한 수치를 모르면 "수십조 원 규모", "과반수 이상" 등 범위형 표현 사용.
   - "73%", "130조 원" 등 구체적 수치는 검증 가능한 경우에만 사용.

# Output Structure (출력 구조 — 100% 준수)
반드시 HTML 형식으로 다음 구조를 순서대로 출력하십시오.

<title>[주제와 관련된 강력한 훅(Hook)을 담은 매혹적인 제목 — 키워드를 앞부분에 포함]</title>

<p>(도입부 — 아래 패턴을 정확히 따를 것) 4~5문장.
{intro_hook}
도입부는 반드시 위 패턴의 지시를 100% 준수하여 작성하십시오.</p>

<div class="key-point"><strong>이 글의 순서</strong><br/>(본문의 핵심 소제목 3~4개를 번호 리스트로 정리)</div>

<h2>1. 기존의 방식이 실패할 수밖에 없는 이유</h2>
<p>(문제 정의) 대중들이 알고 있는 상식의 허점을 데이터와 논리로 반박. 400~600자. <strong> 강조 3개 이상.</p>

<h2>2. [당신이 창작한 독점적 프레임워크 이름] : 본질적 해결책</h2>
<p>(이 글의 핵심 인사이트) 프레임워크의 구조를 단계별로 설명. 비교/정리 <table> 필수. 각 단계마다 구체적 수치/기대효과 포함. 600~800자.</p>

<div class="tip-box"><strong>실전 적용 팁</strong><br/>(독자가 당장 오늘부터 실행할 수 있는 구체적인 액션 플랜 1가지)</div>

<h2>3. [프레임워크] 심화 적용: 성과를 극대화하는 전략</h2>
<p>(프레임워크를 고급 레벨로 확장. 실전 시나리오, 케이스 스터디, 응용 방법. 400~600자.)</p>

<h2>4. 리스크 관리 및 시스템화 전략</h2>
<p>(정보를 아는 것에서 끝나지 않고, 이를 자동화/시스템화하는 전문가적 조언. 400~600자.)</p>

<blockquote><strong>인사이트 팩트 체크</strong><br/>(본문 내용을 뒷받침하는 결정적인 통계, 논리, 또는 전문가의 시각)</blockquote>

<h2>5. 실행 로드맵: 지금 당장 시작하는 3단계</h2>
<p>(구체적인 실행 단계를 <ol>로 정리. 각 단계에 예상 소요시간/비용/기대효과 포함.)</p>

<div class="key-point"><strong>최종 핵심 요약 (Executive Summary)</strong><br/>
(글의 전체 내용을 3줄 요약 + 프레임워크 이름 재언급 + 다음 행동을 유도하는 강력한 클로징)</div>

=== HTML 규칙 (절대 준수) ===
- <title>글제목</title>을 최상단에
- <h2>, <h3>, <p>, <strong>, <ol>/<ul>, <table>, <blockquote> 사용
- <div class="tip-box">, <div class="key-point"> 사용 가능
- <h1> 금지 (워드프레스 자동 생성)
- <table>은 반드시 <thead><tr><th>헤더</th></tr></thead><tbody><tr><td>내용</td></tr></tbody> 구조
- 마크다운 문법 절대 금지: **bold**, ```code```, ## 제목 → HTML 태그만 사용
- <strong> 강조 최소 10개
- 분량: 5,000~7,000자 (군더더기 없이 알차게)
- 연속으로 같은 블록(tip-box, key-point, blockquote) 2개 배치 금지
"""

GOLDEN_POLISH_PROMPT_KO = """아래 블로그 초안을 '업계 탑 전문가의 칼럼' 수준으로 업그레이드하세요.

키워드: {keyword}

=== Golden 폴리싱 규칙 ===
1. **프레임워크 검증**: 독점적 프레임워크 이름이 있는지 확인. 없으면 [영문3자리]+[명사] 형태로 생성하여 삽입.
   프레임워크 이름은 본문에 최소 5회 반복되어야 함 (권위성 확보).
2. **데이터 앵커링 검증**: 도입부 3문장 안에 구체적 수치/통계가 있는지 확인. 없으면 해당 주제의 설득력 있는 데이터를 추가.
3. **감성 제거**: "제 지인", "제가 해봤는데", "여러분", "~거든요", "~해요" 같은 소비자 톤 표현을 모두 제거.
   → 전문가 톤으로 교체 (~합니다, ~하십시오, ~입니다)
4. AI 특유 표현 제거: "다양한", "살펴보겠습니다", "알아보겠습니다", "관심이 높아지고 있습니다"
   → 논리적이고 단정적인 표현으로 100% 교체
5. 번역체 제거: "레버리지", "인사이더 정보", "스케일링" → 한국어 풀어쓰기 또는 괄호 병기
6. 모든 주장에 구체적 수치/비교/출처 필수 (근거 없는 문장 삭제)
7. 전문 용어에 괄호 풀이 확인: "ETF(여러 주식을 한 바구니에 담은 상품)"
8. 구조 검증: 문제 정의 → 프레임워크 해결책 → 심화 → 리스크 → 실행 로드맵 → Executive Summary 순서
9. Executive Summary가 없으면 마지막에 추가 (3줄 요약 + 프레임워크 재언급)
10. <strong> 최소 10개, <table> 1개 이상, key-point/tip-box/blockquote 각 1개 이상
11. HTML 구조 유지. 마크다운 잔재 발견 시 HTML로 교체.
12. 분량 5,000~7,000자 유지. 군더더기 삭제, 부족하면 데이터 기반 콘텐츠 보강.
13. **할루시네이션 검증 (CRITICAL — 반드시 수행)**:
    - 본문에서 "~에 따르면", "~연구", "~보고서", "~조사" 등 인용 표현을 모두 찾아라.
    - 해당 출처가 실존하는지 확인 불가하면 → "일반적으로 알려진 바에 따르면"으로 교체하거나 문장 삭제.
    - 구체적 수치(%, 금액, 건수)가 검증 불가하면 → 범위형 표현("수십%", "상당수")으로 교체.
    - 존재하지 않는 기관명, 학술지명, 법률명이 있으면 즉시 삭제.
    - Google Helpful Content 기준: 가짜 통계 1개 = 사이트 전체 신뢰도 하락.

=== 절대 금지 (출력 형식) ===
- 폴리싱된 HTML 본문만 출력하세요. 그 외 아무것도 출력하지 마세요.
- "수정 내역", "폴리싱 요약", "변경 사항", "수정한 부분" 등 메타 설명 금지
- 인사말, 서문, 맺음말 등 부가 텍스트 금지
- <title>로 시작해서 HTML 본문으로 끝나야 합니다

초안:
{draft}
"""

# ── 니치별 프롬프트 보강 템플릿 ──
NICHE_PROMPT_INJECTION = """
=== 이 글의 스타일 가이드 ({niche_label}) ===
톤: {tone}

이 니치에서 독자가 가장 원하는 가치: {value_focus}
위 가치를 모든 섹션에서 구체적으로 제공하세요.

필수 콘텐츠 블록:
{must_blocks}

이 스타일 가이드를 반드시 따르세요. 톤이 다른 니치와 섞이면 안 됩니다.
"""

# ── 프롬프트 선택 함수 ──
def get_prompts(lang="ko", adsense_mode=False, category="", golden_mode=False):
    """언어/모드/니치에 따라 프롬프트 반환 (니치 스타일 주입 포함)"""
    # Golden 모드 최우선 (Gemini 피드백 3대 전략: 페르소나+프레임워크+데이터앵커링)
    if golden_mode and lang == "ko":
        hook = random.choice(GOLDEN_INTRO_HOOKS)
        draft_tmpl = GOLDEN_DRAFT_PROMPT_KO.replace("{intro_hook}", hook)
        polish_tmpl = GOLDEN_POLISH_PROMPT_KO
    elif adsense_mode:
        if lang == "en":
            draft_tmpl, polish_tmpl = ADSENSE_DRAFT_PROMPT_EN, POLISH_PROMPT_EN
        else:
            draft_tmpl, polish_tmpl = ADSENSE_DRAFT_PROMPT_KO, POLISH_PROMPT_KO
    elif lang == "en":
        draft_tmpl, polish_tmpl = DRAFT_PROMPT_EN, POLISH_PROMPT_EN
    else:
        draft_tmpl, polish_tmpl = DRAFT_PROMPT_KO, POLISH_PROMPT_KO

    # 니치 스타일 주입 (카테고리가 있으면)
    if category and lang == "ko":
        style, group = get_niche_style(category)
        niche_extra = NICHE_PROMPT_INJECTION.format(
            niche_label=style["label"],
            tone=style["tone"],
            value_focus=style.get("value_focus", ""),
            must_blocks=style["must_blocks"],
        )
        draft_tmpl = draft_tmpl.rstrip() + "\n" + niche_extra

    return draft_tmpl, polish_tmpl


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
                 preferred_draft=None, preferred_polish=None, golden_mode=False):
        """멀티모델 폴체인 + 언어/모드 분기 + 모델 선택 반영"""
        # unique_seed는 내부 추적용으로만 사용, 프롬프트에는 주입하지 않음
        if not unique_seed:
            unique_seed = hashlib.md5(
                f"{SITE_ID}-{keyword}-{datetime.now(KST).isoformat()}-{random.random()}".encode()
            ).hexdigest()[:12]

        draft_tmpl, polish_tmpl = get_prompts(lang, adsense_mode, category=category, golden_mode=golden_mode)
        prompt = draft_tmpl.format(keyword=keyword, intent=intent, category=category)

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

        polish_prompt = polish_tmpl.format(keyword=keyword, draft=draft)

        # 폴리싱 모델 체인: preferred_polish → grok → claude → gemini
        polish_chain = []
        if preferred_polish and preferred_polish != "none":
            polish_chain.append(preferred_polish)
        # 기본 폴체인 (초안과 다른 모델 우선)
        for m in ["grok", "claude", "gemini"]:
            if m not in polish_chain and m != draft_model:
                polish_chain.append(m)
        # 같은 모델도 폴백으로 추가
        if draft_model and draft_model not in polish_chain:
            polish_chain.append(draft_model)

        for p_model in polish_chain:
            polished = None
            p_model_name = None
            if p_model in ("grok", "grok-3", "grok-3-mini") and GROK_KEY:
                polished, p_model_name = self._call_grok(polish_prompt)
            elif p_model in ("claude", "claude-sonnet") and CLAUDE_KEY:
                polished = self._call_claude_polish(polish_prompt, model="claude-sonnet-4-20250514")
                p_model_name = "claude-sonnet-4-20250514"
            elif p_model in ("claude-haiku", "haiku") and CLAUDE_KEY:
                polished = self._call_claude_polish(polish_prompt, model="claude-haiku-4-5-20241022")
                p_model_name = "claude-haiku-4-5-20241022"
            elif p_model in ("gemini", "gemini-2.5-flash", "gemini-2.0-flash") and GEMINI_KEY:
                polished, p_model_name = self._call_gemini(polish_prompt)
            if polished and p_model_name:
                polish_cost = self._estimate_cost(p_model_name, polish_prompt, polished)
                log.info(f"폴리싱 완료 [{p_model_name}] ({len(polished)}자)")
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
        # 모델 우선순위: 2.0-flash → 2.0-flash-lite → 1.5-flash
        models = ["gemini-2.0-flash", "gemini-2.0-flash-lite", "gemini-1.5-flash"]
        for model in models:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    log.info(f"Gemini ({model}) 생성 중...{f' (재시도 {attempt+1}/{max_retries})' if attempt else ''}")
                    resp = requests.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}",
                        headers={"Content-Type": "application/json"},
                        json={"contents": [{"parts": [{"text": prompt}]}],
                              "generationConfig": {"temperature": 0.8, "maxOutputTokens": 5000}},
                        timeout=180
                    )
                    if resp.status_code == 429:
                        wait = 30 * (attempt + 1)
                        log.warning(f"Gemini 429 Rate Limit → {wait}초 대기 후 재시도")
                        time.sleep(wait)
                        continue
                    if resp.status_code == 404:
                        log.warning(f"Gemini {model} 404 → 다음 모델 시도")
                        break  # 다음 모델로
                    resp.raise_for_status()
                    data = resp.json()
                    content = data["candidates"][0]["content"]["parts"][0]["text"]
                    usage = data.get("usageMetadata", {})
                    self._log_cost(model, "google", "content",
                                  usage.get("promptTokenCount", 0), usage.get("candidatesTokenCount", 0))
                    return content, model
                except Exception as e:
                    if "429" in str(e) and attempt < max_retries - 1:
                        wait = 30 * (attempt + 1)
                        log.warning(f"Gemini Rate Limit → {wait}초 대기 후 재시도")
                        time.sleep(wait)
                        continue
                    if "404" in str(e):
                        log.warning(f"Gemini {model} 404 → 다음 모델 시도")
                        break  # 다음 모델로
                    log.warning(f"Gemini 실패: {e}")
                    return None, None
        log.warning("Gemini 전체 모델 실패")
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

    def _call_claude_polish(self, prompt, model="claude-sonnet-4-20250514"):
        import requests
        model_label = "Haiku" if "haiku" in model else "Sonnet"
        try:
            log.info(f"Claude {model_label} 폴리싱 중...")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01",
                         "Content-Type": "application/json"},
                json={"model": model, "max_tokens": 6000,
                      "messages": [{"role": "user", "content": prompt}]},
                timeout=180
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["content"][0]["text"]
            usage = data.get("usage", {})
            self._log_cost(model, "anthropic", "polish",
                          usage.get("input_tokens", 0), usage.get("output_tokens", 0))
            return content
        except Exception as e:
            log.warning(f"Claude {model_label} 폴리싱 실패 (초안 그대로 사용): {e}")
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
    품질 채점 기준 (100점 만점) — SEO + 비주얼 통합:
    - 콘텐츠 길이: 20점 (5000자+ = 20, 4000+ = 16, 3000+ = 12, 2000+ = 8, 미만 = 4)
    - H2 소제목 수: 15점 (5~7개 = 15, 4/8 = 12, 3/9 = 8, 기타 = 0)
    - 문단 품질: 10점 (평균 80~400자 = 10, 50~500자 = 7, 기타 = 3)
    - 이미지 포함: 15점 (2장+ = 15, 1장 = 10, 없음 = 0)
    - 키워드 SEO: 10점 (H2에 키워드 2개+ = 10, 1개 = 6, 없음 = 0)
    - <strong> 강조: 5점 (5개+ = 5, 3~4개 = 3, 미만 = 0)
    - CTA 존재: 5점
    - HTML 구조: 5점
    - 비주얼 블록: 15점 (blockquote/tip-box/key-point/table 중 3종+ = 15, 2종 = 10, 1종 = 5, 없음 = 0)
    """

    MIN_SCORE = 85

    def score(self, content, keyword, has_image=False):
        total = 0
        details = {}

        # 1. 콘텐츠 길이 (20점) — 5000자+ 기준 상향
        length = len(re.sub(r'<[^>]+>', '', content))  # 태그 제외 순수 텍스트 길이
        if length >= 5000: pts = 20
        elif length >= 4000: pts = 16
        elif length >= 3000: pts = 12
        elif length >= 2000: pts = 8
        else: pts = 4
        total += pts
        details['length'] = f"{length}자 ({pts}/20)"

        # 2. H2 소제목 수 (15점)
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.IGNORECASE)
        h2_count = len(h2s)
        if 5 <= h2_count <= 7: pts = 15
        elif h2_count in (4, 8): pts = 12
        elif h2_count in (3, 9): pts = 8
        else: pts = 0
        total += pts
        details['h2_count'] = f"{h2_count}개 ({pts}/15)"

        # 3. 문단 품질 (10점)
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', content, re.IGNORECASE | re.DOTALL)
        if paragraphs:
            avg_len = sum(len(re.sub(r'<[^>]+>', '', p)) for p in paragraphs) / len(paragraphs)
            if 80 <= avg_len <= 400: pts = 10
            elif 50 <= avg_len <= 500: pts = 7
            else: pts = 3
        else:
            avg_len = 0
            pts = 0
        total += pts
        details['paragraphs'] = f"{len(paragraphs)}개, 평균 {avg_len:.0f}자 ({pts}/10)"

        # 4. 이미지 포함 (15점) — 다중 이미지 보너스
        img_count = len(re.findall(r'<img\s', content, re.IGNORECASE))
        if not has_image and img_count == 0:
            pts = 0
        elif img_count >= 2 or has_image:
            pts = 15 if img_count >= 2 else 10
        else:
            pts = 10
        total += pts
        details['image'] = f"{img_count}장 ({pts}/15)"

        # 5. 키워드 SEO (10점) — H2 내 키워드 포함
        kw_words = keyword.lower().split()
        kw_in_h2 = sum(1 for h2 in h2s if any(w in h2.lower() for w in kw_words if len(w) > 1))
        pts = 10 if kw_in_h2 >= 2 else (6 if kw_in_h2 == 1 else 0)
        total += pts
        details['seo_keyword'] = f"{kw_in_h2}개 H2 ({pts}/10)"

        # 6. <strong> 강조 (5점) — 기준 상향
        strong_count = len(re.findall(r'<strong', content, re.IGNORECASE))
        pts = 5 if strong_count >= 5 else (3 if strong_count >= 3 else 0)
        total += pts
        details['strong'] = f"{strong_count}개 ({pts}/5)"

        # 7. CTA 존재 (5점)
        cta_patterns = ['확인해', '시작해', '신청', '추천', '클릭', '바로가기', '지금', '놓치지']
        has_cta = any(p in content for p in cta_patterns)
        pts = 5 if has_cta else 0
        total += pts
        details['cta'] = f"{'있음' if has_cta else '없음'} ({pts}/5)"

        # 8. HTML 구조 (5점)
        has_proper = '<h2' in content and '<p' in content and '</p>' in content
        pts = 5 if has_proper else 0
        total += pts
        details['structure'] = f"{'정상' if has_proper else '비정상'} ({pts}/5)"

        # 9. 비주얼 블록 다양성 (15점) — NEW
        visual_types = 0
        if '<blockquote' in content: visual_types += 1
        if 'tip-box' in content or '\U0001f4a1' in content or '실용 팁' in content: visual_types += 1
        if 'key-point' in content or '\U0001f3af' in content or '핵심 포인트' in content: visual_types += 1
        if '<table' in content: visual_types += 1
        if visual_types >= 3: pts = 15
        elif visual_types == 2: pts = 10
        elif visual_types == 1: pts = 5
        else: pts = 0
        total += pts
        details['visual_blocks'] = f"{visual_types}종 ({pts}/15)"

        return total, details

    # ── 신뢰도 검사 (할루시네이션 의심 패턴 감지) ──
    SUSPICIOUS_PATTERNS = [
        # 가짜 기관/연구 인용 패턴
        (r'(?:에 따르면|발표한|조사에서|보고서에|연구에서|분석에 따르면)',
         'citation', '출처 인용 표현 — 실존 여부 확인 필요'),
        # 지나치게 구체적인 퍼센트 (소수점 포함)
        (r'\d{1,2}\.\d+%',
         'precise_pct', '소수점 퍼센트 — 출처 없으면 날조 가능성'),
        # "~대학교 연구팀", "~연구소" 등 가짜 기관명
        (r'(?:대학교|대학|연구소|연구원|학회|협회|재단)\s*(?:의|에서|가|는|연구팀)',
         'institution', '기관명 인용 — 실존 여부 확인 필요'),
        # "20XX년 기준" 미래 또는 최신 통계 주장
        (r'202[5-9]년\s*(?:기준|현재|조사|통계)',
         'future_stat', '최신 연도 통계 — 검증 가능한 데이터인지 확인'),
    ]

    def credibility_audit(self, content):
        """콘텐츠 내 할루시네이션 의심 패턴을 감지하여 경고 목록 반환"""
        plain = re.sub(r'<[^>]+>', '', content)
        warnings = []
        for pattern, tag, desc in self.SUSPICIOUS_PATTERNS:
            matches = re.findall(pattern, plain)
            if matches:
                warnings.append({
                    'tag': tag,
                    'count': len(matches),
                    'desc': desc,
                    'samples': matches[:3]
                })
        return warnings

    def validate(self, content, keyword, has_image=False):
        score, details = self.score(content, keyword, has_image)
        passed = score >= self.MIN_SCORE
        log.info(f"  품질 점수: {score}/100 ({'PASS' if passed else 'FAIL'}, 기준: {self.MIN_SCORE}점)")
        for k, v in details.items():
            log.info(f"    {k}: {v}")
        return passed, score, details


# ═══════════════════════════════════════════════════════
# 4. 이미지 삽입 — 3중 폴백 (Pexels → Pixabay → Unsplash)
# ═══════════════════════════════════════════════════════
class ImageManager:
    """이미지 3중 폴백: Pexels(1순위) → Pixabay(2순위) → Unsplash(백업)"""

    # 한국어 키워드 → 영문 검색어 매핑 (확장)
    KO_EN_FALLBACK = {
        # 금융/재테크
        "대출": "loan finance bank", "보험": "insurance family protection",
        "부동산": "real estate house", "투자": "investment portfolio",
        "주식": "stock market trading", "적금": "savings piggy bank",
        "ETF": "investment ETF chart", "재테크": "financial planning money",
        "연금": "retirement pension", "월급": "salary paycheck office",
        "배당": "dividend investment", "펀드": "fund investment",
        "금리": "interest rate bank", "환율": "currency exchange",
        "자산": "wealth asset management", "포트폴리오": "investment portfolio",
        # 절세/정부
        "세금": "tax accounting calculator", "절세": "tax saving documents",
        "소득세": "income tax filing", "연말정산": "tax refund documents",
        "정부지원": "government support application", "보조금": "subsidy grant money",
        "지원금": "financial aid government", "소상공인": "small business shop",
        # 부업/수익화
        "부업": "side hustle freelance laptop", "수익화": "monetization income laptop",
        "블로그": "blogging laptop writing", "프리랜서": "freelancer working laptop",
        "쿠팡": "online shopping delivery", "어필리에이트": "affiliate marketing laptop",
        "애드센스": "digital advertising website",
        # IT/테크
        "AI": "artificial intelligence robot technology",
        "노트북": "laptop computer workspace", "가성비": "budget value shopping",
        "재택근무": "remote work home office", "생산성": "productivity workspace desk",
        "코딩": "programming coding screen", "개발자": "developer coding screen",
        "앱": "mobile app smartphone", "소프트웨어": "software computer screen",
        "IT": "technology digital", "가전": "home electronics appliance",
        "전자제품": "electronics gadgets", "스마트": "smart technology device",
        "청소기": "vacuum cleaner home", "에어컨": "air conditioner home",
        "건조기": "dryer laundry home", "냉장고": "refrigerator kitchen",
        # 생활경제
        "생활비": "household budget saving", "절약": "saving money frugal",
        "전월세": "apartment rental keys", "월세": "rent apartment living",
        "전세": "apartment lease contract", "계약": "contract signing document",
        "1인 가구": "single living apartment", "자취": "single living cooking",
        "식비": "food budget grocery", "통신비": "mobile phone bill",
        "전기세": "electricity bill saving",
        # 건강
        "건강": "health wellness exercise", "다이어트": "diet fitness healthy",
        "운동": "exercise gym fitness", "실비": "health insurance hospital",
        # 기존
        "요리": "cooking food kitchen", "레시피": "recipe cooking",
        "여행": "travel destination scenery", "호텔": "hotel resort vacation",
        "캠핑": "camping outdoor nature", "육아": "parenting family baby",
        "교육": "education study classroom", "취업": "job career interview",
        "프로그래밍": "programming coding developer", "자동차": "car automotive",
        "인테리어": "interior design home", "패션": "fashion style outfit",
        "뷰티": "beauty skincare cosmetics", "반려동물": "pet dog cat",
        "결혼": "wedding celebration", "이사": "moving house boxes",
        "창업": "startup business entrepreneur",
    }

    # 카테고리 slug → 영문 이미지 검색어 폴백
    CATEGORY_IMAGE_FALLBACK = {
        "ai-tools": "artificial intelligence technology workspace",
        "finance-invest": "investment finance chart money",
        "side-income": "freelancer laptop side hustle income",
        "tech-review": "technology gadgets electronics review",
        "gov-support": "government support application documents",
        "life-economy": "household budget saving money",
        # bomissu 한국어 카테고리 폴백
        "정부지원·복지": "government support family application form",
        "절세·세금": "tax calculator saving documents accounting",
        "부업·수익화": "side hustle freelancer laptop earning money",
        "보험·금융": "insurance finance family protection savings",
        "생활비·살림": "household budget grocery shopping saving money",
    }

    def _to_english_query(self, keyword, category=""):
        """한국어 키워드를 영문 이미지 검색어로 변환"""
        # 이미 영문이면 그대로
        if all(ord(c) < 128 or c == ' ' for c in keyword):
            return keyword

        # 매핑 테이블에서 매칭되는 단어 찾기 (가장 긴 매칭 우선)
        matches = [(ko, en) for ko, en in self.KO_EN_FALLBACK.items() if ko in keyword]
        if matches:
            # 가장 긴 한국어 키워드 매칭 선택 (더 구체적)
            best = max(matches, key=lambda x: len(x[0]))
            return best[1]

        # 카테고리 기반 폴백
        if category:
            cat_query = self.CATEGORY_IMAGE_FALLBACK.get(category)
            if cat_query:
                return cat_query

        # 최종 폴백: 비즈니스/기술 범용 (그라데이션 방지)
        return "business office workspace professional"

    def fetch_image(self, keyword, category=""):
        """3중 폴백으로 이미지 검색 (한국어 키워드 자동 영문 변환)"""
        en_query = self._to_english_query(keyword, category)
        log.info(f"  이미지 검색: '{keyword}' → '{en_query}'")

        # 1순위: Pexels (고품질 무료)
        if PEXELS_KEY:
            result = self._fetch_pexels(en_query)
            if result:
                result["alt"] = keyword  # alt는 원래 한국어 키워드 유지
                return result

        # 2순위: Pixabay (대량 무료)
        if PIXABAY_KEY:
            result = self._fetch_pixabay(en_query)
            if result:
                result["alt"] = keyword
                return result

        # 3순위: Unsplash (백업)
        if UNSPLASH_KEY:
            result = self._fetch_unsplash(en_query)
            if result:
                result["alt"] = keyword
                return result

        # 최종 폴백: Lorem Picsum (API 키 불필요, 항상 작동)
        result = self._fetch_picsum()
        if result:
            result["alt"] = keyword
            return result

        log.warning(f"모든 이미지 API 실패: {keyword} (en: {en_query})")
        return None

    def _fetch_picsum(self):
        """Lorem Picsum — API 키 불필요 무료 이미지 (최종 폴백)"""
        import requests
        try:
            log.info("  Picsum 이미지 폴백 중...")
            seed = random.randint(1, 1000)
            url = f"https://picsum.photos/seed/{seed}/1200/630"
            resp = requests.head(url, allow_redirects=True, timeout=10)
            if resp.status_code == 200:
                final_url = resp.url
                log.info(f"  Picsum 이미지 확보: seed={seed}")
                return {
                    "url": final_url,
                    "credit": "Lorem Picsum",
                    "credit_url": "https://picsum.photos",
                    "source": "picsum",
                }
        except Exception as e:
            log.warning(f"  Picsum 이미지 실패: {e}")
        return None

    def fetch_multiple(self, keyword, count=3, category=""):
        """여러 장의 이미지를 가져와 분산 삽입용으로 반환"""
        en_query = self._to_english_query(keyword, category)
        log.info(f"  이미지 배치 검색: '{keyword}' → '{en_query}' (목표 {count}장)")
        log.info(f"  API 키 상태: Pexels={'O' if PEXELS_KEY else 'X'} | Pixabay={'O' if PIXABAY_KEY else 'X'} | Unsplash={'O' if UNSPLASH_KEY else 'X'}")
        images = []

        # 1순위: Pexels에서 여러 장 가져오기
        if PEXELS_KEY:
            batch = self._fetch_pexels_batch(en_query, count)
            images.extend(batch)
            log.info(f"  Pexels: {len(batch)}장 확보")
        else:
            log.warning("  Pexels API 키 없음 — 스킵")

        # 2순위: Pixabay에서 보충
        if len(images) < count and PIXABAY_KEY:
            batch = self._fetch_pixabay_batch(en_query, count - len(images))
            images.extend(batch)
            log.info(f"  Pixabay: {len(batch)}장 추가 (누적 {len(images)}장)")
        elif len(images) < count:
            log.warning("  Pixabay API 키 없음 — 스킵")

        # 3순위: Unsplash 개별 가져오기
        if len(images) < count and UNSPLASH_KEY:
            for _ in range(count - len(images)):
                result = self._fetch_unsplash(en_query)
                if result:
                    images.append(result)
            log.info(f"  Unsplash 보충 후 누적: {len(images)}장")
        elif len(images) < count:
            log.warning("  Unsplash API 키 없음 — 스킵")

        # 최종 폴백: Picsum (API 키 불필요, 항상 작동)
        if len(images) < count:
            log.info(f"  API 이미지 부족 ({len(images)}/{count}) → Picsum 폴백 시작")
        while len(images) < count:
            result = self._fetch_picsum()
            if result:
                result["alt"] = keyword
                images.append(result)
            else:
                break

        # alt 태그를 한국어 키워드로 설정
        for img in images:
            img["alt"] = keyword

        log.info(f"  이미지 최종 {len(images)}장 확보 (목표: {count}장)")
        return images

    def _fetch_pexels(self, query):
        import requests
        try:
            log.info("  Pexels 이미지 검색 중...")
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": query, "per_page": 5, "orientation": "landscape", "size": "large"},
                timeout=10
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            if photos:
                img = random.choice(photos[:3])
                log.info(f"  Pexels 이미지 확보: {img['photographer']}")
                return {
                    "url": img["src"]["large2x"],
                    "alt": query,
                    "credit": img["photographer"],
                    "link": img["photographer_url"],
                    "source": "Pexels"
                }
        except Exception as e:
            log.warning(f"  Pexels 실패: {e}")
        return None

    def _fetch_pexels_batch(self, query, count):
        """Pexels에서 여러 장 가져오기 (중복 방지)"""
        import requests
        results = []
        try:
            resp = requests.get(
                "https://api.pexels.com/v1/search",
                headers={"Authorization": PEXELS_KEY},
                params={"query": query, "per_page": max(count * 2, 8), "orientation": "landscape", "size": "large"},
                timeout=10
            )
            resp.raise_for_status()
            photos = resp.json().get("photos", [])
            random.shuffle(photos)
            for img in photos[:count]:
                results.append({
                    "url": img["src"]["large2x"],
                    "alt": query,
                    "credit": img["photographer"],
                    "link": img["photographer_url"],
                    "source": "Pexels"
                })
        except Exception as e:
            log.warning(f"  Pexels batch 실패: {e}")
        return results

    def _fetch_pixabay(self, query):
        import requests
        try:
            log.info("  Pixabay 이미지 검색 중...")
            resp = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_KEY, "q": query, "per_page": 5,
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
                    "alt": query,
                    "credit": img.get("user", "Pixabay"),
                    "link": img.get("pageURL", "https://pixabay.com"),
                    "source": "Pixabay"
                }
        except Exception as e:
            log.warning(f"  Pixabay 실패: {e}")
        return None

    def _fetch_pixabay_batch(self, query, count):
        """Pixabay에서 여러 장 가져오기"""
        import requests
        results = []
        try:
            resp = requests.get(
                "https://pixabay.com/api/",
                params={
                    "key": PIXABAY_KEY, "q": query, "per_page": max(count * 2, 8),
                    "orientation": "horizontal", "image_type": "photo",
                    "min_width": 1200, "safesearch": "true"
                },
                timeout=10
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
            random.shuffle(hits)
            for img in hits[:count]:
                results.append({
                    "url": img["largeImageURL"],
                    "alt": query,
                    "credit": img.get("user", "Pixabay"),
                    "link": img.get("pageURL", "https://pixabay.com"),
                    "source": "Pixabay"
                })
        except Exception as e:
            log.warning(f"  Pixabay batch 실패: {e}")
        return results

    def _fetch_unsplash(self, query):
        import requests
        try:
            log.info("  Unsplash 이미지 검색 중 (백업)...")
            resp = requests.get(
                "https://api.unsplash.com/search/photos",
                headers={"Authorization": f"Client-ID {UNSPLASH_KEY}"},
                params={"query": query, "per_page": 3, "orientation": "landscape"},
                timeout=10
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if results:
                img = random.choice(results[:3])
                log.info(f"  Unsplash 이미지 확보: {img['user']['name']}")
                return {
                    "url": img["urls"]["regular"],
                    "alt": img.get("alt_description", query),
                    "credit": img["user"]["name"],
                    "link": img["user"]["links"]["html"],
                    "source": "Unsplash"
                }
        except Exception as e:
            log.warning(f"  Unsplash 실패: {e}")
        return None

    def _make_figure_html(self, image_data):
        """이미지 데이터로 프리미엄 figure HTML 생성"""
        source = image_data.get("source", "Unknown")
        return (
            f'<figure style="margin:32px 0">'
            f'<img src="{image_data["url"]}" alt="{image_data["alt"]}" '
            f'style="width:100%;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.12)" loading="lazy"/>'
            f'<figcaption style="text-align:center;font-size:12px;color:#94a3b8;margin-top:10px;">'
            f'Photo by <a href="{image_data["link"]}?utm_source=autoblog" target="_blank" '
            f'style="color:#64748b;text-decoration:none">'
            f'{image_data["credit"]}</a> on {source}</figcaption>'
            f'</figure>'
        )

    def insert_image(self, content, image_data):
        """콘텐츠 첫 번째 H2 앞에 이미지 삽입"""
        if not image_data:
            return content, False, ""

        img_html = self._make_figure_html(image_data)
        source = image_data.get("source", "Unknown")

        if "<h2" in content:
            idx = content.index("<h2")
            return content[:idx] + img_html + content[idx:], True, source
        return img_html + content, True, source

    def insert_multiple_images(self, content, images):
        """여러 이미지를 H2 섹션 사이에 균등 분산 삽입"""
        if not images:
            return content, False, ""

        h2_positions = [m.start() for m in re.finditer(r'<h2', content, re.IGNORECASE)]
        if len(h2_positions) < 2:
            # H2가 1개 이하면 첫 이미지만 삽입
            return self.insert_image(content, images[0])

        # 이미지를 H2 섹션 사이에 균등 분배
        # 첫 번째 이미지: 첫 H2 앞, 나머지: H2 섹션 사이에 분산
        interval = max(1, len(h2_positions) // (len(images)))
        insert_positions = []
        for i, img in enumerate(images):
            h2_idx = min(i * interval, len(h2_positions) - 1)
            insert_positions.append((h2_positions[h2_idx], img))

        # 뒤에서부터 삽입 (앞에서 삽입하면 인덱스가 밀림)
        insert_positions.sort(key=lambda x: x[0], reverse=True)
        for pos, img in insert_positions:
            img_html = self._make_figure_html(img)
            content = content[:pos] + img_html + content[pos:]

        sources = list({img.get("source", "Unknown") for img in images})
        return content, True, "+".join(sources)


# ═══════════════════════════════════════════════════════
# 5. 제휴 링크 삽입
# ═══════════════════════════════════════════════════════
class AffiliateManager:
    def __init__(self, global_cfg=None):
        self.links_file = DATA / "affiliates.json"
        self.links = self._load()
        self.global_cfg = global_cfg or {}
        self.manual_coupang = self.global_cfg.get("coupang_manual_products", [])
        self.tenping_campaigns = self.global_cfg.get("tenping_campaigns", [])

    def _load(self):
        if self.links_file.exists():
            with open(self.links_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"coupang": {}, "cpa": {}, "adsense_slots": []}

    def insert_links(self, content, keyword, category, stage=1):
        if stage < 2:
            return content, False

        has_coupang = False
        matched = []

        # 기존 affiliates.json 매칭
        coupang = self.links.get("coupang", {})
        for cat_key, items in coupang.items():
            if cat_key in keyword or cat_key in category:
                for item in items:
                    if "YOUR_" not in item.get("url", "YOUR_"):
                        matched.append(item)

        # 수동 등록 쿠팡 상품 매칭
        for product in self.manual_coupang:
            prod_cat = product.get("category", "")
            if prod_cat and (prod_cat in keyword or prod_cat in category):
                matched.append({"name": product["name"], "url": product["url"]})

        if matched:
            items_html = ""
            for m in matched[:3]:
                items_html += (
                    f'<li style="margin:8px 0">'
                    f'<a href="{m["url"]}" target="_blank" rel="nofollow sponsored" '
                    f'style="color:#6366f1;text-decoration:none;font-weight:600">'
                    f'{m["name"]} 최저가 확인하기</a></li>'
                )
            box = (
                f'\n<div style="background:#f8f9ff;border:2px solid #dde3ff;'
                f'border-radius:12px;padding:20px;margin:24px 0">'
                f'<p style="font-weight:700;font-size:16px;margin:0 0 12px">추천 상품</p>'
                f'<ul style="list-style:none;padding:0;margin:0">{items_html}</ul>'
                f'</div>\n'
            )
            # 첫 번째 H2 앞에 삽입
            import re as _re
            h2_match = _re.search(r'<h2', content)
            if h2_match:
                content = content[:h2_match.start()] + box + content[h2_match.start():]
            else:
                content += box
            has_coupang = True

            # 쿠팡 고지문 (중복 방지)
            if '쿠팡 파트너스' not in content:
                content += (
                    '<p style="font-size:12px;color:#999;margin:24px 0 0;padding:12px;'
                    'background:#f8f8f8;border-radius:8px">'
                    '이 포스팅은 쿠팡 파트너스 활동의 일환으로, '
                    '이에 따른 일정액의 수수료를 제공받습니다.</p>'
                )

        # 텐핑 CPA 삽입 (Stage 2+)
        tenping_matched = []
        for campaign in self.tenping_campaigns:
            camp_cat = campaign.get("category", "")
            if camp_cat and (camp_cat in keyword or camp_cat in category):
                tenping_matched.append(campaign)

        if tenping_matched:
            import re as _re
            tp_items = ""
            for c in tenping_matched[:2]:
                tp_items += (
                    f'<li style="margin:8px 0">'
                    f'<a href="{c["url"]}" target="_blank" rel="nofollow sponsored" '
                    f'style="color:#ff6b35;text-decoration:none;font-weight:600">'
                    f'{c["name"]} 자세히 보기</a></li>'
                )
            tp_box = (
                f'\n<div style="background:#fff8f0;border:2px solid #ffe0c0;'
                f'border-radius:12px;padding:20px;margin:24px 0">'
                f'<p style="font-weight:700;font-size:16px;margin:0 0 12px">추천 서비스</p>'
                f'<ul style="list-style:none;padding:0;margin:0">{tp_items}</ul>'
                f'</div>\n'
            )
            # 두 번째 H2 뒤에 삽입
            h2_positions = [m.end() for m in _re.finditer(r'</h2>', content)]
            if len(h2_positions) >= 2:
                pos = h2_positions[1]
                content = content[:pos] + tp_box + content[pos:]
            else:
                content += tp_box

        return content, has_coupang


# ═══════════════════════════════════════════════════════
# 6. AdSense HTML 최적화 — 발행 전 후처리
# ═══════════════════════════════════════════════════════

# 모바일 반응형 CSS (글 본문에 인라인 주입)
INLINE_MOBILE_CSS = """<style>
/* AutoBlog Mobile Responsive */
.entry-content { max-width: 100% !important; padding: 0 !important; box-sizing: border-box; }
.entry-content img { max-width: 100% !important; height: auto !important; border-radius: 8px; }
.entry-content table { width: 100% !important; display: block; overflow-x: auto; -webkit-overflow-scrolling: touch; border-collapse: collapse; font-size: 14px; }
.entry-content th, .entry-content td { padding: 10px 12px; border: 1px solid #e2e8f0; }
.entry-content th { font-weight: 700; color: #1a1a2e; }
.entry-content thead th { background: #6366f1; color: #fff !important; }
.entry-content table[style*="box-shadow"] thead th { background: none; }
.entry-content blockquote { margin: 16px 0; padding: 16px 20px; border-left: 4px solid #6366f1; background: #f8fafc; border-radius: 0 8px 8px 0; }
.entry-content .tip-box { padding: 16px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 10px; margin: 16px 0; }
.entry-content .key-point { padding: 16px; background: #fefce8; border: 1px solid #fde68a; border-radius: 10px; margin: 16px 0; }
.entry-content ul, .entry-content ol { padding-left: 20px; }
.entry-content li { margin-bottom: 6px; }
.entry-content h2 { font-size: 22px; font-weight: 800; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 2px solid #f1f5f9; }
.entry-content h3 { font-size: 18px; font-weight: 700; margin: 24px 0 12px; }
.entry-content p { margin-bottom: 16px; line-height: 1.8; }
@media (max-width: 768px) {
  .entry-content h2 { font-size: 19px; margin: 24px 0 12px; }
  .entry-content h3 { font-size: 16px; }
  .entry-content p { font-size: 15px; line-height: 1.8; }
  .entry-content { font-size: 15px; }
  .site-main, .content-area, .inside-article { padding: 0 6px !important; }
  .grid-container { padding: 0 4px !important; }
}
@media (max-width: 480px) {
  .entry-content h2 { font-size: 17px; }
  .entry-content p { font-size: 14px; }
  .entry-content { font-size: 14px; }
}
</style>"""

class AdSenseOptimizer:
    """발행 전 HTML 구조를 AdSense 친화적으로 정리"""

    def optimize(self, content):
        # 0. HTML 문서 껍데기 제거 (AI가 생성하거나 수동 편집으로 삽입된 경우)
        content = re.sub(r'<!DOCTYPE\s+html[^>]*>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'</?html[^>]*>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<head[^>]*>.*?</head>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r'</?body[^>]*>', '', content, flags=re.IGNORECASE)
        content = re.sub(r'<meta[^>]*/?>', '', content, flags=re.IGNORECASE)

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

        # 5. 모바일 반응형 CSS 인라인 주입 — 비활성화 (AdSense 승인 대비)
        # Customizer 전역 CSS(inject_css.py)로 대체. 인라인 CSS는 Google 품질 신호에 악영향.
        # if '<style' not in content[:200]:
        #     content = INLINE_MOBILE_CSS + "\n" + content

        return content

    def _generate_toc(self, content):
        """H2 기반 프리미엄 목차 생성"""
        h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', content, re.IGNORECASE)
        if len(h2s) < 4:
            return ""

        items = ""
        for i, h2 in enumerate(h2s, 1):
            clean = re.sub(r'<[^>]+>', '', h2).strip()
            items += (
                f'<li style="margin:6px 0;padding:6px 12px;border-radius:8px;'
                f'transition:background 0.2s">'
                f'<a href="#section-{i}" style="color:#4338ca;text-decoration:none;'
                f'font-size:14px;font-weight:500;display:block">{clean}</a></li>'
            )

        return (
            f'<div style="background:linear-gradient(135deg,#f5f3ff,#ede9fe);'
            f'border:1px solid #c4b5fd;border-radius:16px;'
            f'padding:20px 24px;margin:24px 0;box-shadow:0 2px 8px rgba(99,102,241,0.08)">'
            f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
            f'<span style="font-size:18px">\U0001f4d1</span>'
            f'<span style="font-weight:800;font-size:15px;color:#1a1a2e">이 글의 순서</span></div>'
            f'<ol style="margin:0;padding-left:24px;color:#4a5568;list-style:none;counter-reset:toc-counter">'
            f'{items}</ol></div>\n'
        )


# ═══════════════════════════════════════════════════════
# 7. WordPress 발행
# ═══════════════════════════════════════════════════════
class WordPressPublisher:
    def __init__(self):
        import base64
        # wp_url에서 /wp-json/wp/v2 접미사 제거 (중복 방지)
        url = WP_URL.rstrip("/")
        if url.endswith("/wp-json/wp/v2"):
            url = url[:-len("/wp-json/wp/v2")]
        self.url = url
        cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {cred}",
            "Content-Type": "application/json"
        }

    def _get_site_name(self):
        """WordPress 사이트 이름 조회 (캐싱)"""
        if hasattr(self, '_site_name_cache'):
            return self._site_name_cache
        import requests
        try:
            resp = requests.get(f"{self.url}/wp-json", headers=self.headers, timeout=10)
            self._site_name_cache = resp.json().get("name", "")
        except Exception:
            self._site_name_cache = ""
        return self._site_name_cache

    def publish(self, title, content, category="", tags=None,
                slug="", focus_keyword="", meta_description=""):
        import requests
        cat_id = self._get_or_create_category(category) if category else None

        post_data = {"title": title, "content": content, "status": "publish", "format": "standard"}
        if cat_id:
            post_data["categories"] = [cat_id]
        if tags:
            tag_ids = [self._get_or_create_tag(t) for t in tags[:5]]
            post_data["tags"] = [t for t in tag_ids if t]
        if slug:
            post_data["slug"] = slug

        # Rank Math SEO meta
        site_name = self._get_site_name()
        seo_meta = {}
        if focus_keyword:
            seo_meta["rank_math_focus_keyword"] = focus_keyword
            seo_title_suffix = f" | {site_name}" if site_name else ""
            seo_meta["rank_math_title"] = f"{title}{seo_title_suffix}"
        if meta_description:
            seo_meta["rank_math_description"] = meta_description
        # SEO robots: index, follow (명시적 설정)
        seo_meta["rank_math_robots"] = "a]index,a]follow,a]max-snippet:-1,a]max-image-preview:large,a]max-video-preview:-1"
        if seo_meta:
            post_data["meta"] = seo_meta

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

    # 카테고리 이름 → slug 매핑 (& 문자 검색 문제 방지)
    _CAT_SLUG_MAP = {
        "AI 도구 & 생산성": "ai-tools",
        "재테크 & 투자": "finance-invest",
        "부업 & 수익화": "side-income",
        "IT & 테크 리뷰": "tech-review",
        "정부지원 & 절세": "gov-support",
        "생활 경제": "life-economy",
        # bomissu.com 생활경제 카테고리
        "정부지원·복지": "gov-support",
        "절세·세금": "tax-saving",
        "부업·수익화": "side-income",
        "보험·금융": "insurance-finance",
        "생활비·살림": "living-cost",
    }

    def _get_or_create_category(self, name):
        import requests, html as _html
        try:
            slug = self._CAT_SLUG_MAP.get(name)

            # 1순위: slug 기반 조회 (& 문자 안전)
            if slug:
                resp = requests.get(f"{self.url}/wp-json/wp/v2/categories",
                                   headers=self.headers, params={"slug": slug}, timeout=10)
                cats = resp.json()
                if cats:
                    return cats[0]["id"]

            # 2순위: name 검색 폴백
            resp = requests.get(f"{self.url}/wp-json/wp/v2/categories",
                               headers=self.headers, params={"search": name, "per_page": 5}, timeout=10)
            for c in resp.json():
                if _html.unescape(c["name"]).lower() == name.lower():
                    cat_id = c["id"]
                    # 한국어 slug → 영문 slug 자동 교정
                    if slug and c.get("slug", "").startswith("%"):
                        try:
                            requests.post(f"{self.url}/wp-json/wp/v2/categories/{cat_id}",
                                         headers=self.headers, json={"slug": slug}, timeout=10)
                            log.info(f"  카테고리 slug 교정: {name} → {slug}")
                        except Exception:
                            pass
                    return cat_id

            # 3순위: 새로 생성 (항상 영문 slug 포함)
            create_data = {"name": name}
            if slug:
                create_data["slug"] = slug
            resp = requests.post(f"{self.url}/wp-json/wp/v2/categories",
                                headers=self.headers, json=create_data, timeout=10)
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
    """프리미엄 비주얼 스타일링 엔진 — 12종 콘텐츠 블록 + AI 표현 치환"""

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

    # ── 프리미엄 스타일 정의 ──

    H2_STYLE = (
        'style="font-size:23px;font-weight:800;color:#1a1a2e;'
        'margin:48px 0 20px;padding:16px 0 12px;'
        'border-bottom:3px solid transparent;'
        'background-image:linear-gradient(#fff,#fff),linear-gradient(135deg,#6366f1,#3b82f6);'
        'background-origin:padding-box,border-box;background-clip:padding-box,border-box;'
        'border-bottom:3px solid #6366f1"'
    )

    H3_STYLE = (
        'style="font-size:18px;font-weight:700;color:#334155;'
        'margin:28px 0 12px;padding-left:12px;'
        'border-left:4px solid #6366f1"'
    )

    P_STYLE = 'style="line-height:1.95;color:#374151;margin:18px 0;font-size:16.5px;word-break:keep-all"'

    # 팁 박스: 밝은 파란 배경 + 전구 아이콘
    TIP_BOX_STYLE = (
        'style="background:linear-gradient(135deg,#eff6ff,#dbeafe);'
        'border:1px solid #93c5fd;border-radius:12px;padding:20px 24px;margin:28px 0;'
        'position:relative;overflow:hidden"'
    )
    TIP_BOX_LABEL = (
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
        '<span style="font-size:20px">\U0001f4a1</span>'
        '<span style="font-weight:700;color:#1d4ed8;font-size:14px;letter-spacing:0.5px">'
        '\uc2e4\uc6a9 \ud301</span></div>'
    )

    # 핵심 포인트: 보라색 좌측 보더 + 밝은 배경
    KEY_POINT_STYLE = (
        'style="background:#f5f3ff;border-left:4px solid #6366f1;'
        'border-radius:0 12px 12px 0;padding:18px 24px;margin:28px 0"'
    )
    KEY_POINT_LABEL = (
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
        '<span style="font-size:18px">\U0001f3af</span>'
        '<span style="font-weight:700;color:#6366f1;font-size:14px;letter-spacing:0.5px">'
        '\ud575\uc2ec \ud3ec\uc778\ud2b8</span></div>'
    )

    # 인용구 (blockquote): 도파민 트리거 디자인
    BLOCKQUOTE_STYLE = (
        'style="background:linear-gradient(135deg,#fefce8,#fef9c3);'
        'border-left:4px solid #eab308;border-radius:0 12px 12px 0;'
        'padding:20px 24px;margin:28px 0;font-style:normal;color:#92400e"'
    )
    BLOCKQUOTE_LABEL = (
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
        '<span style="font-size:18px">\u2728</span>'
        '<span style="font-weight:700;color:#92400e;font-size:14px;letter-spacing:0.5px">'
        '\ub180\ub77c\uc6b4 \uc0ac\uc2e4</span></div>'
    )

    # 테이블 스타일
    TABLE_STYLE = (
        'style="width:100%;border-collapse:separate;border-spacing:0;'
        'border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);'
        'margin:28px 0;font-size:15px"'
    )
    THEAD_STYLE = 'style="background:linear-gradient(135deg,#6366f1,#818cf8)"'
    TH_STYLE = 'style="padding:14px 16px;color:#fff !important;font-weight:700;text-align:left;font-size:14px;background:none"'
    TD_STYLE = 'style="padding:12px 16px;border-bottom:1px solid #e2e8f0;color:#374151"'
    TD_ALT_STYLE = 'style="padding:12px 16px;border-bottom:1px solid #e2e8f0;color:#374151;background:#f8fafc"'

    # 리스트 스타일
    UL_STYLE = 'style="margin:16px 0;padding-left:0;list-style:none"'
    LI_STYLE = (
        'style="padding:8px 0 8px 28px;position:relative;line-height:1.8;color:#374151;font-size:15.5px"'
    )
    LI_BULLET = (
        'style="position:absolute;left:0;top:10px;width:18px;height:18px;'
        'background:linear-gradient(135deg,#6366f1,#818cf8);border-radius:50%;'
        'display:inline-flex;align-items:center;justify-content:center;'
        'color:#fff;font-size:10px;font-weight:700"'
    )

    OL_STYLE = 'style="margin:16px 0;padding-left:0;list-style:none;counter-reset:ol-counter"'
    OL_LI_STYLE = (
        'style="padding:10px 0 10px 40px;position:relative;line-height:1.8;'
        'color:#374151;font-size:15.5px;counter-increment:ol-counter"'
    )

    # CTA 박스: 그라디언트 + 아이콘
    CTA_BOX = (
        '\n<div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);'
        'border-radius:16px;padding:28px 32px;margin:40px 0;text-align:center;'
        'box-shadow:0 8px 32px rgba(99,102,241,0.25)">\n'
        '<p style="color:#fff;font-size:20px;font-weight:800;margin:0 0 10px">'
        '\U0001f680 \uc9c0\uae08 \ubc14\ub85c \ud655\uc778\ud574\ubcf4\uc138\uc694</p>\n'
        '<p style="color:rgba(255,255,255,0.9);margin:0;font-size:15px;line-height:1.6">'
        '\uc704 \ub0b4\uc6a9\uc744 \ucc38\uace0\ud574\uc11c \ub098\uc5d0\uac8c \ub9de\ub294 \uc120\ud0dd\uc744 \ud574\ubcf4\uc138\uc694</p>\n'
        '</div>\n'
    )

    # 구분선
    SECTION_DIVIDER = (
        '<div style="text-align:center;margin:40px 0;color:#cbd5e1;font-size:20px;letter-spacing:12px">'
        '\u00b7\u00b7\u00b7</div>'
    )

    # 동그라미 숫자 매핑 (1~20)
    CIRCLED_NUMS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

    def format(self, content, keyword="", category=""):
        """프리미엄 콘텐츠 후처리 파이프라인 (니치별 색상 분기)"""
        original_len = len(content)

        # 니치 색상 오버라이드
        self._apply_niche_colors(category)

        # Phase 0: 마크다운 잔재 → HTML 변환 (AI가 MD를 섞어 출력하는 경우 대응)
        content = self._md_to_html(content)
        content = self._replace_ai_expressions(content)

        # Phase 1: 시맨틱 블록 스타일링
        content = self._style_tip_box(content)
        content = self._style_key_point(content)
        content = self._style_blockquote(content)
        content = self._style_table(content)
        content = self._style_lists(content)

        # Phase 2: 기본 태그 스타일링
        content = self._style_h2(content)
        content = self._style_h3(content)
        content = self._style_p(content)
        content = self._style_strong(content)
        content = self._ensure_cta(content)

        # Phase 3: 정리
        content = self._remove_duplicate_blocks(content)
        content = self._dashes_to_circled_nums(content)
        content = self._clean_empty_tags(content)

        # Phase 4: Rank Math SEO 최적화
        content = self._optimize_seo(content, keyword)

        style, group = get_niche_style(category) if category else (NICHE_STYLES["product"], "product")
        changes = len(content) - original_len
        log.info(f"   프리미엄 스타일링 완료: [{style['label']}] 12종 블록 + SEO ({changes:+d}자)")
        return content

    def _optimize_seo(self, content, keyword):
        """Rank Math SEO 점수 최적화 (80점+ 목표)"""
        if not keyword:
            return content
        import re

        kw_lower = keyword.lower()

        # 1. 첫 문단에 focus keyword 포함 확인 → 없으면 삽입
        first_p_match = re.search(r'<p[^>]*>(.*?)</p>', content, re.DOTALL)
        if first_p_match and kw_lower not in first_p_match.group(1).lower():
            old_p = first_p_match.group(0)
            inner = first_p_match.group(1)
            new_p = old_p.replace(inner, f'{inner} <strong>{keyword}</strong>에 대해 알아보겠습니다.')
            content = content.replace(old_p, new_p, 1)

        # 2. 이미지 alt 태그에 keyword 포함
        def _add_keyword_alt(match):
            tag = match.group(0)
            alt_match = re.search(r'alt="([^"]*)"', tag)
            if alt_match:
                current_alt = alt_match.group(1)
                if kw_lower not in current_alt.lower():
                    new_alt = f'{current_alt} - {keyword}' if current_alt else keyword
                    tag = tag.replace(f'alt="{current_alt}"', f'alt="{new_alt}"')
            else:
                tag = tag.replace('<img ', f'<img alt="{keyword}" ')
            return tag

        content = re.sub(r'<img[^>]+>', _add_keyword_alt, content)

        return content

    def _apply_niche_colors(self, category):
        """니치별 액센트 색상으로 스타일 변수 동적 교체"""
        if not category:
            return

        style, group = get_niche_style(category)
        accent = style["accent"]
        accent_light = style["accent_light"]
        gradient = style["accent_gradient"]

        # H2: 그라디언트 언더라인 색상
        self.H2_STYLE = (
            f'style="font-size:23px;font-weight:800;color:#1a1a2e;'
            f'margin:48px 0 20px;padding:16px 0 12px;'
            f'border-bottom:3px solid {accent}"'
        )

        # H3: 좌측 보더 색상
        self.H3_STYLE = (
            f'style="font-size:18px;font-weight:700;color:#334155;'
            f'margin:28px 0 12px;padding-left:12px;'
            f'border-left:4px solid {accent}"'
        )

        # 테이블 헤더
        self.THEAD_STYLE = f'style="background:{gradient}"'

        # CTA 그라디언트
        self.CTA_BOX = (
            f'\n<div style="background:{gradient};'
            f'border-radius:16px;padding:28px 32px;margin:40px 0;text-align:center;'
            f'box-shadow:0 8px 32px {accent}40">\n'
            f'<p style="color:#fff;font-size:20px;font-weight:800;margin:0 0 10px">'
            f'\U0001f680 \uc9c0\uae08 \ubc14\ub85c \ud655\uc778\ud574\ubcf4\uc138\uc694</p>\n'
            f'<p style="color:rgba(255,255,255,0.9);margin:0;font-size:15px;line-height:1.6">'
            f'\uc704 \ub0b4\uc6a9\uc744 \ucc38\uace0\ud574\uc11c \ub098\uc5d0\uac8c \ub9de\ub294 \uc120\ud0dd\uc744 \ud574\ubcf4\uc138\uc694</p>\n'
            f'</div>\n'
        )

        # strong 하이라이트 색상
        self._strong_bg = f"{accent_light}"
        self._table_accent = accent

        # 뉴스 그룹: blockquote를 빨간 톤으로
        if group == "news":
            self.BLOCKQUOTE_STYLE = (
                'style="background:linear-gradient(135deg,#fef2f2,#fee2e2);'
                'border-left:4px solid #dc2626;border-radius:0 12px 12px 0;'
                'padding:20px 24px;margin:28px 0;font-style:normal;color:#991b1b"'
            )
            self.BLOCKQUOTE_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:18px">\U0001f4e2</span>'
                '<span style="font-weight:700;color:#991b1b;font-size:14px;letter-spacing:0.5px">'
                '\ud575\uc2ec \ud329\ud2b8</span></div>'
            )

        # 섹터 그룹: blockquote를 시안 톤으로 + 전문가 분석 라벨
        elif group == "sector":
            self.BLOCKQUOTE_STYLE = (
                'style="background:linear-gradient(135deg,#ecfeff,#cffafe);'
                'border-left:4px solid #0891b2;border-radius:0 12px 12px 0;'
                'padding:20px 24px;margin:28px 0;font-style:normal;color:#155e75"'
            )
            self.BLOCKQUOTE_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:18px">\U0001f4ca</span>'
                '<span style="font-weight:700;color:#155e75;font-size:14px;letter-spacing:0.5px">'
                '\uc804\ubb38\uac00 \ubd84\uc11d</span></div>'
            )

        # 정보 서비스: blockquote를 녹색 톤으로 + 알림 라벨
        elif group == "info":
            self.BLOCKQUOTE_STYLE = (
                'style="background:linear-gradient(135deg,#ecfdf5,#d1fae5);'
                'border-left:4px solid #059669;border-radius:0 12px 12px 0;'
                'padding:20px 24px;margin:28px 0;font-style:normal;color:#065f46"'
            )
            self.BLOCKQUOTE_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:18px">\u2705</span>'
                '<span style="font-weight:700;color:#065f46;font-size:14px;letter-spacing:0.5px">'
                '\uc54c\uc544\ub450\uba74 \uc720\ub9ac\ud55c \uc815\ubcf4</span></div>'
            )

        # 홍보: blockquote를 핑크 톤으로
        elif group == "promo":
            self.BLOCKQUOTE_STYLE = (
                'style="background:linear-gradient(135deg,#fdf4ff,#fae8ff);'
                'border-left:4px solid #d946ef;border-radius:0 12px 12px 0;'
                'padding:20px 24px;margin:28px 0;font-style:normal;color:#86198f"'
            )
            self.BLOCKQUOTE_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:18px">\U0001f4ac</span>'
                '<span style="font-weight:700;color:#86198f;font-size:14px;letter-spacing:0.5px">'
                '\uc2e4\uc0ac\uc6a9\uc790 \ud6c4\uae30</span></div>'
            )

        # 라이프스타일 (bomissu): 코랄 핑크 따뜻한 톤
        elif group == "lifestyle":
            self.BLOCKQUOTE_STYLE = (
                'style="background:linear-gradient(135deg,#FFF5F0,#FFF0F5);'
                'border-left:4px solid #E8796B;border-radius:0 12px 12px 0;'
                'padding:20px 24px;margin:28px 0;font-style:normal;color:#5A3A3A"'
            )
            self.BLOCKQUOTE_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:18px">\U0001f338</span>'
                '<span style="font-weight:700;color:#E8796B;font-size:14px;letter-spacing:0.5px">'
                '놓치면 손해!</span></div>'
            )
            # 팁 박스: 부드러운 피치
            self.TIP_BOX_STYLE = (
                'style="background:linear-gradient(135deg,#FFF5F0,#FFEEE8);'
                'border:1px solid #F4A89A;border-radius:12px;padding:20px 24px;margin:28px 0;'
                'position:relative;overflow:hidden"'
            )
            self.TIP_BOX_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
                '<span style="font-size:20px">\U0001f4a1</span>'
                '<span style="font-weight:700;color:#E8796B;font-size:14px;letter-spacing:0.5px">'
                '알아두면 좋은 꿀팁</span></div>'
            )
            # 핵심 포인트: 연한 코랄 배경
            self.KEY_POINT_STYLE = (
                'style="background:#FFF0ED;border-left:4px solid #E8796B;'
                'border-radius:0 12px 12px 0;padding:18px 24px;margin:28px 0"'
            )
            self.KEY_POINT_LABEL = (
                '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
                '<span style="font-size:18px">\U0001f3af</span>'
                '<span style="font-weight:700;color:#E8796B;font-size:14px;letter-spacing:0.5px">'
                '핵심 포인트</span></div>'
            )
            # 리스트 불릿: 코랄 핑크 그라데이션
            self.LI_BULLET = (
                'style="position:absolute;left:0;top:10px;width:18px;height:18px;'
                'background:linear-gradient(135deg,#E8796B,#F4A89A);border-radius:50%;'
                'display:inline-flex;align-items:center;justify-content:center;'
                'color:#fff;font-size:10px;font-weight:700"'
            )
            # 테이블: 연한 코랄 헤더
            self.THEAD_STYLE = 'style="background:linear-gradient(135deg,#FDDCD7,#FAC8D4)"'
            self.TH_STYLE = (
                'style="padding:14px 16px;color:#5A3A3A !important;font-weight:700;'
                'text-align:left;font-size:14px;background:none"'
            )
            self.TD_ALT_STYLE = (
                'style="padding:12px 16px;border-bottom:1px solid #FDDCD7;color:#374151;background:#FFF8F6"'
            )
            self.TD_STYLE = (
                'style="padding:12px 16px;border-bottom:1px solid #FDDCD7;color:#374151"'
            )

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

    def _style_tip_box(self, content):
        """<div class="tip-box"> → 프리미엄 팁 박스"""
        def _replace_tip(m):
            inner = m.group(1).strip()
            # 내부 p 태그의 스타일 적용
            inner = _re.sub(r'<p[^>]*>', f'<p style="margin:0;line-height:1.7;color:#1e40af;font-size:15px">', inner)
            return (
                f'<div {self.TIP_BOX_STYLE}>'
                f'{self.TIP_BOX_LABEL}'
                f'{inner}</div>'
            )
        return _re.sub(
            r'<div\s+class="tip-box"[^>]*>(.*?)</div>',
            _replace_tip, content, flags=_re.DOTALL | _re.IGNORECASE
        )

    def _style_key_point(self, content):
        """<div class="key-point"> → 프리미엄 핵심 포인트 박스 (번호 줄바꿈 포함)"""
        def _replace_kp(m):
            inner = m.group(1).strip()
            # 내부 p 태그 스타일
            inner = _re.sub(r'<p[^>]*>', f'<p style="margin:0;line-height:1.8;color:#4338ca;font-size:15px;font-weight:600">', inner)
            # ①②③ 등 동그라미 숫자 앞에 줄바꿈 삽입 (첫 번째 제외)
            inner = _re.sub(r'(?<!^)\s*([①②③④⑤⑥⑦⑧⑨⑩])', r'<br/>\1', inner)
            return (
                f'<div {self.KEY_POINT_STYLE}>'
                f'{self.KEY_POINT_LABEL}'
                f'{inner}</div>'
            )
        return _re.sub(
            r'<div\s+class="key-point"[^>]*>(.*?)</div>',
            _replace_kp, content, flags=_re.DOTALL | _re.IGNORECASE
        )

    def _style_blockquote(self, content):
        """<blockquote> → 깔끔한 인사이트 인용구 (내부 정리 포함)"""
        def _replace_bq(m):
            inner = m.group(1).strip()
            # 내부 불필요한 태그/마크다운 정리
            inner = _re.sub(r'<p[^>]*>', '', inner)
            inner = inner.replace('</p>', '<br/>')
            inner = _re.sub(r'<br/>\s*$', '', inner)
            inner = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', inner)
            # 깔끔한 단일 p로 감싸기
            inner_styled = (
                f'<p style="margin:0;line-height:1.8;font-size:15px;font-weight:500;'
                f'color:inherit">{inner}</p>'
            )
            return (
                f'<blockquote {self.BLOCKQUOTE_STYLE}>'
                f'{self.BLOCKQUOTE_LABEL}'
                f'{inner_styled}</blockquote>'
            )
        return _re.sub(
            r'<blockquote[^>]*>(.*?)</blockquote>',
            _replace_bq, content, flags=_re.DOTALL | _re.IGNORECASE
        )

    def _style_table(self, content):
        """테이블에 프리미엄 스타일 적용 — thead 없어도 첫 행을 헤더로 처리"""
        accent = getattr(self, '_table_accent', '#6366f1')
        table_style = self.TABLE_STYLE

        # 모든 <table>...</table> 블록을 개별 처리
        tables = list(re.finditer(r'<table[^>]*>(.*?)</table>', content, re.DOTALL | re.IGNORECASE))
        # 뒤에서부터 교체 (인덱스 밀림 방지)
        for m in reversed(tables):
            table_inner = m.group(1)

            # Step 1: thead가 없으면 첫 번째 tr → thead로 변환
            if '<thead' not in table_inner.lower():
                first_tr = re.search(r'<tr[^>]*>(.*?)</tr>', table_inner, re.DOTALL | re.IGNORECASE)
                if first_tr:
                    cells = first_tr.group(1)
                    cells = re.sub(r'<td[^>]*>', '<th>', cells, flags=re.IGNORECASE)
                    cells = cells.replace('</td>', '</th>')
                    header = f'<thead><tr>{cells}</tr></thead>'
                    rest = table_inner[first_tr.end():]
                    table_inner = header + '<tbody>' + rest + '</tbody>'

            # Step 2: thead 배경 (th/td보다 먼저 — regex 충돌 방지)
            table_inner = re.sub(
                r'<thead[^>]*>',
                f'<thead style="background:#f1f5f9;border-bottom:2px solid {accent}">',
                table_inner, flags=re.IGNORECASE
            )

            # Step 3: th 스타일 (진한 글씨 + 밝은 배경 — 흰 배경에서도 항상 보임)
            table_inner = re.sub(
                r'<th(?!ead)(?:\s[^>]*)?>',
                f'<th style="padding:14px 16px;color:#1a1a2e;font-weight:700;text-align:left;font-size:14px;background:#f1f5f9">',
                table_inner, flags=re.IGNORECASE
            )

            # Step 4: td 스타일 — (?!body)로 <tbody> 제외
            td_idx = [0]
            def _td_style(tm):
                td_idx[0] += 1
                bg = '#f8fafc' if (td_idx[0] // 4) % 2 == 1 else '#ffffff'
                return f'<td style="padding:12px 16px;border-bottom:1px solid #e2e8f0;color:#1a1a2e;background:{bg}">'
            table_inner = re.sub(r'<td(?!body)(?:\s[^>]*)?>',  _td_style, table_inner, flags=re.IGNORECASE)

            replacement = f'<table {table_style}>{table_inner}</table>'
            content = content[:m.start()] + replacement + content[m.end():]

        return content

    def _style_lists(self, content):
        """ul/ol 리스트에 프리미엄 스타일 적용"""
        # ul 스타일 (팁박스/키포인트 내부의 ul은 제외)
        content = _re.sub(
            r'<ul(?:\s[^>]*)?>(?!\s*</)',
            f'<ul {self.UL_STYLE}>',
            content, flags=_re.IGNORECASE
        )

        # ol 스타일
        content = _re.sub(
            r'<ol(?:\s[^>]*)?>(?!\s*</)',
            f'<ol {self.OL_STYLE}>',
            content, flags=_re.IGNORECASE
        )

        # li에 커스텀 불릿 스타일 (ul 내부만 — 간단하게 전체 li에 패딩 적용)
        def _replace_li(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<li', f'<li {self.LI_STYLE}', 1)
        content = _re.sub(r'<li[^>]*>', _replace_li, content, flags=_re.IGNORECASE)

        return content

    def _style_h2(self, content):
        """스타일 없는 H2에 프리미엄 스타일 적용"""
        def _replace_h2(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<h2', f'<h2 {self.H2_STYLE}', 1)

        return _re.sub(r'<h2[^>]*>', _replace_h2, content, flags=_re.IGNORECASE)

    def _style_h3(self, content):
        """스타일 없는 H3에 스타일 적용"""
        def _replace_h3(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<h3', f'<h3 {self.H3_STYLE}', 1)

        return _re.sub(r'<h3[^>]*>', _replace_h3, content, flags=_re.IGNORECASE)

    def _style_p(self, content):
        """스타일 없는 p에 기본 스타일 적용"""
        def _replace_p(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return tag.replace('<p', f'<p {self.P_STYLE}', 1)

        return _re.sub(r'<p(?:\s[^>]*)?>',  _replace_p, content, flags=_re.IGNORECASE)

    def _style_strong(self, content):
        """<strong> 태그에 형광펜 하이라이트 (니치별 색상)"""
        highlight_bg = getattr(self, '_strong_bg', '#fef9c3')
        # lifestyle(bomissu) → 코랄 핑크 형광펜, 기본 → 노랑
        highlight_color = '#FFE0D6' if highlight_bg == '#FFF0ED' else highlight_bg
        def _replace_strong(m):
            tag = m.group(0)
            if 'style=' in tag:
                return tag
            return f'<strong style="color:#1a1a2e;background:linear-gradient(transparent 55%,{highlight_color} 55%);padding:0 2px">'
        return _re.sub(r'<strong[^>]*>', _replace_strong, content, flags=_re.IGNORECASE)

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

    def _md_to_html(self, content):
        """마크다운 잔재를 HTML로 변환 (AI가 MD 문법을 섞어 출력할 때)"""
        # 코드 블록 (```...```) → 제거 (블로그에 코드블록 불필요)
        content = _re.sub(r'```[\w]*\n?(.*?)```', r'<pre style="background:#f1f5f9;border-radius:8px;padding:16px;font-size:13px;overflow-x:auto;margin:16px 0;color:#334155">\1</pre>', content, flags=_re.DOTALL)

        # **bold** → <strong> (이미 <strong>이 아닌 경우)
        content = _re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)

        # *italic* → <em> (단, ** 제외)
        content = _re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', content)

        # 마크다운 제목 잔재 (## / ### 등)
        content = _re.sub(r'^#{2,3}\s+(.+)$', r'<h2>\1</h2>', content, flags=_re.MULTILINE)

        md_fixes = 0
        for pattern in [r'\*\*', r'```', r'^#{2,}']:
            if _re.search(pattern, content):
                md_fixes += 1
        if md_fixes:
            log.info(f"   마크다운 잔재 {md_fixes}종 HTML 변환")
        return content

    def _remove_duplicate_blocks(self, content):
        """연속/인접 동일 블록 중복 제거 + 전체 글에서 같은 타입 최대 2개"""
        for label in ['핵심 포인트', '실용 팁', '놀라운 사실', '핵심 팩트', '전문가 분석',
                       '알아두면 유리한 정보', '실사용자 후기']:
            # 연속된 같은 라벨 블록 → 첫 번째만 유지
            pattern = (
                f'({_re.escape(label)}</span></div>.*?</div>)'
                r'\s*'
                f'(<div[^>]*>.*?{_re.escape(label)}</span></div>.*?</div>)'
            )
            content = _re.sub(pattern, r'\1', content, flags=_re.DOTALL)

        # 전체 글에서 동일 라벨이 3회 이상이면 3번째부터 제거
        for label in ['핵심 포인트', '실용 팁']:
            occurrences = list(_re.finditer(f'{_re.escape(label)}', content))
            if len(occurrences) > 4:  # 라벨 + 내부 텍스트 합산으로 4회 이상이면 중복
                # 마지막 블록 제거 (블록 단위로 찾기 어려우므로 로그만)
                log.info(f"   {label} {len(occurrences)}회 감지 — 중복 주의")

        return content

    def _dashes_to_circled_nums(self, content):
        """<li> 내부의 대시(–/-) 리스트를 동그라미 숫자로 변환"""
        def _replace_dashes_in_block(text):
            counter = [0]
            def _dash_to_num(m):
                if counter[0] < len(self.CIRCLED_NUMS):
                    num = self.CIRCLED_NUMS[counter[0]]
                    counter[0] += 1
                    return num + ' '
                return m.group(0)
            return _re.sub(r'(?:^|\n)\s*[–\-]\s+', _dash_to_num, text)

        # <p> 태그 내부의 연속 대시 리스트 변환
        def _replace_in_p(m):
            tag = m.group(1)
            inner = m.group(2)
            # 대시가 2개 이상 있는 경우만 변환
            dash_count = len(_re.findall(r'[–\-]\s+', inner))
            if dash_count >= 2:
                inner = _replace_dashes_in_block(inner)
            return f'{tag}{inner}'

        content = _re.sub(
            r'(<p[^>]*>)(.*?(?:[–\-]\s+.*?){2,})',
            _replace_in_p, content, flags=_re.DOTALL
        )
        return content

    def _clean_empty_tags(self, content):
        """빈 태그, 불필요한 공백, HTML 문서 태그 정리"""
        # AI가 생성한 HTML 문서 껍데기 제거
        content = _re.sub(r'<!DOCTYPE\s+html[^>]*>', '', content, flags=_re.IGNORECASE)
        content = _re.sub(r'</?html[^>]*>', '', content, flags=_re.IGNORECASE)
        content = _re.sub(r'</?head[^>]*>.*?</head>', '', content, flags=_re.IGNORECASE | _re.DOTALL)
        content = _re.sub(r'</?body[^>]*>', '', content, flags=_re.IGNORECASE)
        content = _re.sub(r'<meta[^>]*/?>', '', content, flags=_re.IGNORECASE)
        # 빈 태그 정리
        content = _re.sub(r'<p[^>]*>\s*</p>', '', content)
        content = _re.sub(r'\n{3,}', '\n\n', content)
        return content


# ═══════════════════════════════════════════════════════
# 12. 메인 파이프라인
# ═══════════════════════════════════════════════════════
# ── AdSense 승인 전 금지 패턴 ──

# Stage 1(AdSense 승인 전)에서 발행되면 안 되는 콘텐츠 패턴
ADSENSE_BANNED_PATTERNS = [
    # 제휴/광고 링크 관련
    (r'쿠팡\s*파트너스', 'coupang_partners'),
    (r'이\s*포스팅은.*일환으로.*수수료', 'affiliate_disclosure'),
    (r'rel="nofollow\s*sponsored"', 'sponsored_link'),
    (r'href="https?://link\.coupang\.com', 'coupang_link'),
    (r'href="https?://[^"]*tenping', 'tenping_link'),
    (r'추천\s*상품.*최저가\s*확인', 'product_recommend'),
    # CPA/CPS 프로모션
    (r'텐핑\s*(CPA|캠페인|오퍼|제휴)', 'tenping_cpa'),
    (r'(수수료|커미션).*제공', 'commission_mention'),
    # 과도한 광고성 표현
    (r'(지금\s*바로|즉시)\s*클릭', 'click_bait'),
    (r'(한정\s*수량|오늘만|마감\s*임박)', 'urgency_spam'),
]

# 제거 대상 HTML 블록 패턴
ADSENSE_BANNED_BLOCKS = [
    r'<div[^>]*>.*?추천\s*상품.*?</div>',
    r'<div[^>]*>.*?쿠팡\s*파트너스.*?</div>',
    r'<p[^>]*>.*?이\s*포스팅은.*?수수료.*?</p>',
    r'<div[^>]*>.*?텐핑.*?자세히\s*보기.*?</div>',
]


def _check_adsense_violations(content, title=""):
    """Stage 1에서 금지 패턴 검출. 위반 목록 반환."""
    import re as _re
    violations = []
    check_text = title + " " + content
    for pattern, tag in ADSENSE_BANNED_PATTERNS:
        if _re.search(pattern, check_text, _re.IGNORECASE):
            violations.append(tag)
    return violations


def _remove_adsense_violations(content):
    """Stage 1에서 금지 HTML 블록 자동 제거."""
    import re as _re
    for block_pattern in ADSENSE_BANNED_BLOCKS:
        content = _re.sub(block_pattern, '', content, flags=_re.IGNORECASE | _re.DOTALL)
    # sponsored 링크를 일반 텍스트로 변환
    content = _re.sub(
        r'<a[^>]*rel="nofollow\s*sponsored"[^>]*>(.*?)</a>',
        r'\1', content, flags=_re.IGNORECASE
    )
    return content


def _sanitize_title(title):
    """제목에서 해시값, 기술적 코드 등 오염 패턴 제거"""
    import re as _re
    # 12자리 hex 해시 제거 (예: dc3c547487a0, fa774c6a4d84)
    title = _re.sub(r'\b[0-9a-f]{12}\b', '', title)
    # 괄호 안 해시 제거 (예: "(dc3c547487a0)")
    title = _re.sub(r'\([0-9a-f]{10,}\)', '', title)
    # "태그" 프리픽스 제거
    title = _re.sub(r'^태그\s*', '', title)
    # 연속 공백/콤마/콜론 정리
    title = _re.sub(r'\s*,\s*,', ',', title)
    title = _re.sub(r':\s*-\s*', ': ', title)
    title = _re.sub(r':\s*,', ':', title)
    title = _re.sub(r'\s{2,}', ' ', title)
    return title.strip().strip(':').strip(',').strip()


def extract_title(content):
    match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
    if match:
        title = _sanitize_title(match.group(1).strip())
        content = re.sub(r"<title>.*?</title>", "", content, flags=re.IGNORECASE)
        return title, content
    match = re.search(r"<h2[^>]*>(.*?)</h2>", content, re.IGNORECASE)
    if match:
        return _sanitize_title(match.group(1).strip()), content
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
        data = resp.json()
        if not isinstance(data, list):
            log.warning(f"sites 테이블 응답이 리스트가 아님: {type(data).__name__}")
            return []
        return [s for s in data if isinstance(s, dict)] or []
    except Exception:
        return []


def should_run_now(site_config=None):
    """사이트별 또는 글로벌 스케줄 설정과 현재 시각 비교. 해당 안 되면 False."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return True

    import requests

    # 사이트별 스케줄 우선, 없으면 글로벌 폴백
    settings = {}
    site_cfg = (site_config or {}).get("config") or {}
    if site_cfg.get("daily_count") and site_cfg.get("schedule_times"):
        settings = site_cfg
    else:
        try:
            resp = requests.get(
                f"{SUPABASE_URL}/rest/v1/dashboard_config?id=eq.global",
                headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
                timeout=10
            )
            rows = resp.json()
            if rows and len(rows) > 0:
                settings = rows[0].get("settings", {})
        except Exception:
            return True

    sel_days = settings.get("selDays")
    sel_times = settings.get("selTimes") or settings.get("schedule_times")
    if not sel_days and not sel_times:
        return True  # 스케줄 미설정 → 항상 실행

    tz_id = settings.get("tz", "KST")
    tz_offsets = {"KST": 9, "EST": -5, "CST": -6, "PST": -8}
    offset = tz_offsets.get(tz_id, 9)
    now = datetime.now(timezone(timedelta(hours=offset)))
    current_day = now.weekday()  # 0=월 ~ 6=일
    current_h, current_m = now.hour, now.minute
    slot = f"{current_h:02d}:{'00' if current_m < 30 else '30'}"

    if sel_days and current_day not in sel_days:
        log.info(f"스케줄 게이트: 오늘({current_day})은 발행일이 아닙니다 (설정: {sel_days})")
        return False
    if sel_times and slot not in sel_times:
        log.info(f"스케줄 게이트: 현재({slot})는 발행 시간이 아닙니다 (설정: {sel_times})")
        return False
    return True


def run_pipeline(count=5, dry_run=False, pipeline="autoblog", site_override=None, adsense_mode=False, golden_mode=False, cli_draft_model="", cli_polish_model="", niches=None):
    """단일 사이트 파이프라인. site_override가 있으면 해당 사이트 설정 사용."""
    global SITE_ID, WP_URL, WP_USER, WP_PASS

    # 사이트 설정 로드 (DB 값 → 환경변수 폴백)
    if site_override:
        SITE_ID = site_override["id"]
        WP_URL = site_override.get("wp_url", "") or WP_URL
        cfg = site_override.get("config") or {}
        WP_USER = cfg.get("wp_username", "") or WP_USER
        WP_PASS = cfg.get("wp_app_password", "") or WP_PASS
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

    # 유효 설정: CLI > 사이트DB > 글로벌 > 기본값
    effective_lang = site_cfg.get("lang", global_cfg.get("lang", "ko"))
    effective_draft_model = cli_draft_model or ai_cfg.get("draft_model", site_cfg.get("draft_model"))
    effective_polish_model = cli_polish_model or ai_cfg.get("polish_model", site_cfg.get("polish_model"))
    # Stage 기반 설정
    monetization_stage = int(global_cfg.get("monetization_stage", 1))
    stage_cfg = STAGE_CONFIG.get(monetization_stage, STAGE_CONFIG[1])
    effective_adsense = stage_cfg["adsense_mode"]
    if adsense_mode:  # CLI --adsense-mode override
        effective_adsense = True

    # 골든타임 모드: Golden 전용 프롬프트 (Gemini 3대 전략) + Claude 폴리싱 + 품질 90+
    if golden_mode:
        # Golden 프롬프트 사용 (adsense_mode와 독립 — get_prompts에서 golden_mode 우선)
        stage_cfg = {**stage_cfg, "quality_min": 90}
        effective_polish_model = None  # Claude 폴리싱 항상 활성화
        log.info("  [GOLDEN MODE] 전문가 페르소나 + 프레임워크 네이밍 + 데이터 앵커링")

    log.info(f"  수익화 단계: Stage {monetization_stage} (품질 {stage_cfg['quality_min']}+)")

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

    # 대시보드 스케줄 게이트: 현재 시각이 발행 시간대가 아니면 스킵
    # --force 플래그 시 게이트 무시 (대시보드 수동 실행)
    force_run = os.environ.get("FORCE_RUN", "false").lower() == "true"
    if not dry_run and not force_run and not should_run_now(site_config):
        return

    if not site_override:
        check_api_status()

    km = KeywordManager(site_id=SITE_ID)
    _site_niches = km.keywords.get("niches", [])  # 키워드 파일의 사이트별 니치
    dkg = DynamicKeywordGenerator(site_niches=_site_niches)
    cg = ContentGenerator()
    cf = ContentFormatter()
    im = ImageManager()
    am = AffiliateManager(global_cfg=global_cfg)
    ao = AdSenseOptimizer()
    qg = QualityGate()
    qg.MIN_SCORE = stage_cfg["quality_min"]
    nc = NaverCafePublisher()
    wp = WordPressPublisher()
    sb = SupabaseLogger()

    # 니치 리스트: 글마다 랜덤 선택
    niche_list = niches or []
    if niche_list:
        log.info(f"  니치 풀: {niche_list} (글마다 랜덤 선택)")

    # 1순위: 정적 keywords.json — 니치별로 분산 선택
    if niche_list:
        keywords = []
        per_niche = max(1, count // len(niche_list))
        remainder = count - per_niche * len(niche_list)
        random.shuffle(niche_list)
        for idx, n in enumerate(niche_list):
            n_count = per_niche + (1 if idx < remainder else 0)
            kws = km.select(count=n_count, pipeline=pipeline, niche=n, kw_mix=stage_cfg["kw_mix"])
            keywords.extend(kws)
        random.shuffle(keywords)
        keywords = keywords[:count]
    else:
        keywords = km.select(count=count, pipeline=pipeline, kw_mix=stage_cfg["kw_mix"])

    # 2순위: 동적 키워드 생성 폴백 (정적 키워드 소진 시)
    if not keywords:
        log.info("  정적 키워드 소진 → 동적 키워드 자동 보충")
        if niche_list:
            keywords = []
            for n in niche_list:
                kws_gen = dkg._generate_for_niche(n, max(1, count // len(niche_list)))
                keywords.extend(kws_gen)
            random.shuffle(keywords)
            keywords = keywords[:count]
        else:
            keywords = dkg.generate(count=count, fallback=True)

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
        # unique_seed: 명시적 _seed가 없으면 SITE_ID + keyword + timestamp로 자동 생성
        unique_seed = kw_data.get("_seed", "")
        if not unique_seed:
            unique_seed = hashlib.md5(
                f"{SITE_ID}-{keyword}-{datetime.now(KST).isoformat()}-{random.random()}".encode()
            ).hexdigest()[:12]

        log.info(f"\n{'='*50}")
        log.info(f"[{i}/{len(keywords)}] '{keyword}' ({kw_type})")
        if kw_data.get("_angle"):
            log.info(f"  앵글: {kw_data['_angle']} / 포맷: {kw_data.get('_format', '')} / 타겟: {kw_data.get('_target', '')}")
        log.info(f"{'='*50}")

        # Step 0.5: 카니발라이제이션 검사
        cannibal_conflicts = km.check_cannibalization(keyword)
        cannibal_score = cannibal_conflicts[0][1] if cannibal_conflicts else 0.0
        if cannibal_conflicts:
            top_conflict = cannibal_conflicts[0]
            log.warning(f"  카니발라이제이션 경고: '{top_conflict[0]}' (유사도 {top_conflict[1]})")
            if cannibal_score >= 0.8:
                log.warning(f"  → 유사도 {cannibal_score} >= 0.8 — 높은 중복 위험")
                sb.log_alert(
                    f"키워드 중복: {keyword}",
                    f"기존 '{top_conflict[0]}'과 유사도 {top_conflict[1]}. 카니발라이제이션 위험.",
                    "warning", "cannibal_high"
                )

        # Step 1: AI 글 생성
        content, cost_usd, content_length = cg.generate(
            keyword, intent, category, unique_seed,
            lang=effective_lang, adsense_mode=effective_adsense,
            preferred_draft=effective_draft_model, preferred_polish=effective_polish_model,
            golden_mode=golden_mode
        )
        if not content:
            fail += 1
            sb.log_publish({"keyword": keyword, "status": "failed",
                           "error_message": "AI 글 생성 실패", "pipeline": pipeline})
            continue

        log.info(f"글 생성 완료 ({content_length}자)")

        # Step 1.5: Python 후처리 (스타일링 + AI 표현 치환)
        content = cf.format(content, keyword=keyword, category=category)
        content_length = len(content)

        # Step 2: 제목 추출
        title, content = extract_title(content)
        log.info(f"제목: {title}")

        # Step 3: 다중 이미지 삽입 (2~3장 분산)
        images = im.fetch_multiple(keyword, count=3, category=category)
        if images:
            content, has_image, image_source = im.insert_multiple_images(content, images)
            img_data = images[0]  # 품질 재검증용 (기존 호환)
            log.info(f"이미지 {len(images)}장 분산 삽입 [{image_source}]")
        else:
            # 폴백: 단일 이미지라도 시도
            img_data = im.fetch_image(keyword, category=category)
            content, has_image, image_source = im.insert_image(content, img_data)
            if has_image:
                log.info(f"이미지 1장 삽입 [{image_source}]")

        # Step 4: 제휴 링크 삽입
        content, has_coupang = am.insert_links(content, keyword, category, stage=monetization_stage)
        if has_coupang:
            log.info(f"  제휴 링크 삽입 완료 (Stage {monetization_stage})")
        elif monetization_stage == 1:
            log.info("  Stage 1 — 제휴 링크 스킵")

        # Step 5: AdSense HTML 최적화
        content = ao.optimize(content)
        log.info("AdSense HTML 최적화 완료")

        # Step 6: 품질 검증 (통합 85점 기준)
        min_score = qg.MIN_SCORE  # 85점
        passed, quality_score, q_details = qg.validate(content, keyword, has_image)
        passed = quality_score >= min_score

        # 미달 시 최대 2회 재생성 (모든 모드)
        if not passed:
            for retry in range(2):
                log.info(f"  품질 재생성 ({retry+1}/2) — {quality_score}점 < {min_score}점")
                content2, cost2, len2 = cg.generate(
                    keyword, intent, category, "",
                    lang=effective_lang, adsense_mode=effective_adsense,
                    preferred_draft=effective_draft_model, preferred_polish=effective_polish_model,
                    golden_mode=golden_mode
                )
                if content2:
                    content2 = cf.format(content2, keyword=keyword)
                    title2, content2 = extract_title(content2)
                    if images:
                        content2, _, _ = im.insert_multiple_images(content2, images)
                    elif img_data:
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
            log.warning(f"품질 미달 ({quality_score}/{min_score}) — 발행 진행")
            sb.log_alert(
                f"품질 미달: {keyword}",
                f"점수 {quality_score}/{min_score}. 항목: {json.dumps(q_details, ensure_ascii=False)[:300]}",
                "warning", "quality_low"
            )

        # Step 6.5: 신뢰도 검사 (할루시네이션 의심 패턴)
        cred_warnings = qg.credibility_audit(content)
        if cred_warnings:
            warn_summary = "; ".join(f"{w['tag']}({w['count']}건)" for w in cred_warnings)
            log.warning(f"  신뢰도 경고: {warn_summary}")
            sb.log_alert(
                f"신뢰도 경고: {keyword}",
                f"할루시네이션 의심 패턴 감지: {warn_summary}. "
                f"상세: {json.dumps(cred_warnings, ensure_ascii=False)[:500]}",
                "warning", "credibility_warning"
            )

        # Step 6.6: AdSense 승인 전 금지 패턴 체크 (Stage 1에서만)
        if monetization_stage == 1:
            adsense_violations = _check_adsense_violations(content, title)
            if adsense_violations:
                violation_summary = "; ".join(adsense_violations)
                log.warning(f"  AdSense 금지 패턴 감지: {violation_summary}")
                # 금지 패턴 자동 제거
                content = _remove_adsense_violations(content)
                sb.log_alert(
                    f"AdSense 패턴 제거: {keyword}",
                    f"Stage 1(승인 전)에서 금지 패턴 자동 제거: {violation_summary}",
                    "warning", "adsense_violation"
                )

        # Step 6.7: 내부 링크 자동 삽입 (SEO 강화)
        content = _insert_internal_links(content, wp, keyword)

        # Step 7: 발행
        if dry_run:
            log.info(f"[DRY RUN] 발행 스킵: {title} (품질: {quality_score}/100)")
            km.mark_used(keyword)
            success += 1
            continue

        # SEO: slug와 메타 정보 설정
        seo_slug = kw_data.get("slug", "")
        seo_focus = kw_data.get("focus_keyword", keyword)
        import re as _re
        _plain = _re.sub(r'<[^>]+>', '', content)
        # 메타 설명: 키워드 데이터 우선, 없으면 첫 문장 2~3개 추출 (150~160자)
        if kw_data.get("meta_description"):
            seo_meta_desc = kw_data["meta_description"]
        else:
            _sentences = [s.strip() for s in _re.split(r'[.!?。]\s+', _plain[:500]) if len(s.strip()) > 10]
            _desc = ". ".join(_sentences[:3])
            seo_meta_desc = (_desc[:157] + "...") if len(_desc) > 160 else _desc

        result = wp.publish(title, content, category=category,
                           tags=[keyword, category] if category else [keyword],
                           slug=seo_slug, focus_keyword=seo_focus,
                           meta_description=seo_meta_desc)

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
                "cannibal_score": cannibal_score,
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

    # SEO: 발행 완료 후 사이트맵 핑 (Google, Bing, IndexNow)
    if success > 0 and not dry_run:
        _ping_sitemaps(WP_URL)

    _git_commit_used()


def _insert_internal_links(content, wp_publisher, current_keyword):
    """기존 발행 글 중 관련 글 2~3개를 본문 하단에 내부 링크로 삽입"""
    import requests as _req
    try:
        # 최근 발행 글 20개 조회 (현재 글 제외)
        resp = _req.get(
            f"{wp_publisher.url}/wp-json/wp/v2/posts?per_page=20&status=publish&orderby=date&order=desc",
            headers=wp_publisher.headers, timeout=10
        )
        if resp.status_code != 200:
            return content
        posts = resp.json()
        if not posts or len(posts) < 2:
            return content

        # 키워드와 관련 있는 글 필터 (제목에 공통 단어가 2개 이상)
        current_words = set(current_keyword.lower().split())
        related = []
        for p in posts:
            p_title = p.get("title", {}).get("rendered", "")
            p_link = p.get("link", "")
            if not p_title or not p_link:
                continue
            p_words = set(p_title.lower().split())
            common = current_words & p_words
            if len(common) >= 1 and p_title.lower() != current_keyword.lower():
                related.append({"title": p_title, "url": p_link, "score": len(common)})

        # 관련도 순 정렬, 없으면 최근 글 3개
        if related:
            related.sort(key=lambda x: x["score"], reverse=True)
            picks = related[:3]
        else:
            picks = [{"title": p["title"]["rendered"], "url": p["link"]} for p in posts[:3]]

        if not picks:
            return content

        # 관련 글 HTML 블록 생성
        links_html = '\n'.join(
            f'<li><a href="{p["url"]}">{p["title"]}</a></li>' for p in picks
        )
        related_block = (
            f'\n<div class="related-posts" style="margin-top:32px;padding:20px 24px;'
            f'background:#f8f9fa;border-radius:12px;border-left:4px solid #d4a853;">'
            f'\n<h3 style="margin:0 0 12px;font-size:16px;">관련 글 더 읽기</h3>'
            f'\n<ul style="margin:0;padding-left:20px;">\n{links_html}\n</ul>'
            f'\n</div>\n'
        )

        # FAQ 섹션 앞 또는 본문 마지막에 삽입
        import re
        faq_match = re.search(r'<div class="faq-section">', content)
        if faq_match:
            insert_pos = faq_match.start()
            content = content[:insert_pos] + related_block + content[insert_pos:]
        else:
            content = content + related_block

        log.info(f"  내부 링크 {len(picks)}개 삽입")
    except Exception as e:
        log.warning(f"  내부 링크 삽입 실패 (무시): {e}")
    return content


def _ping_sitemaps(wp_url):
    """발행 완료 후 검색엔진에 사이트맵 변경 알림"""
    import requests as _req
    if not wp_url:
        return

    domain = wp_url.rstrip("/")
    # Rank Math 사이트맵 우선, WordPress 기본 폴백
    sitemap_candidates = [
        f"{domain}/sitemap_index.xml",
        f"{domain}/wp-sitemap.xml",
        f"{domain}/sitemap.xml",
    ]

    sitemap_url = None
    for candidate in sitemap_candidates:
        try:
            r = _req.head(candidate, timeout=5, allow_redirects=True)
            if r.status_code == 200:
                sitemap_url = candidate
                break
        except Exception:
            continue

    if not sitemap_url:
        log.warning("사이트맵을 찾을 수 없습니다.")
        return

    # Google Ping
    try:
        _req.get(f"https://www.google.com/ping?sitemap={sitemap_url}", timeout=10)
        log.info(f"  Google 사이트맵 핑 완료: {sitemap_url}")
    except Exception:
        log.warning("  Google 핑 실패 (무시)")

    # Bing/IndexNow Ping
    try:
        _req.get(f"https://www.bing.com/ping?sitemap={sitemap_url}", timeout=10)
        log.info(f"  Bing 사이트맵 핑 완료")
    except Exception:
        log.warning("  Bing 핑 실패 (무시)")


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
# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="AutoBlog Engine v6.0")
    parser.add_argument("--count", type=int, default=5, help="발행 편수 (사이트별)")
    parser.add_argument("--dry-run", action="store_true", help="발행 없이 테스트")
    parser.add_argument("--pipeline", default="autoblog", help="파이프라인 (autoblog/hotdeal/promo)")
    parser.add_argument("--adsense-mode", action="store_true", help="AdSense 승인용 고품질 모드 (85점+, 재생성)")
    parser.add_argument("--site-id", default="", help="특정 사이트 ID 지정 (기본: SITE_ID 환경변수)")
    parser.add_argument("--setup-pages", action="store_true", help="AdSense 필수 페이지 자동 생성")
    parser.add_argument("--check-status", action="store_true", help="API 연결 상태 체크 → Supabase 기록")
    parser.add_argument("--site-name", default="", help="사이트 이름 (필수 페이지용)")
    parser.add_argument("--email", default="contact@example.com", help="연락처 이메일")
    parser.add_argument("--niche", default="", help="니치/카테고리 필터 (재테크, 투자, 대출 등)")
    parser.add_argument("--polish", action="store_true", help="Claude AI 폴리싱 활성화 (비용 증가)")
    parser.add_argument("--golden", action="store_true", help="골든타임 모드: 고품질 프롬프트 + Claude 폴리싱 + 품질 90+ 기준")
    parser.add_argument("--force", action="store_true", help="스케줄 게이트 무시 (대시보드 수동 실행용)")
    parser.add_argument("--draft-model", default="", help="초안 모델 (grok/gemini/deepseek)")
    parser.add_argument("--polish-model", default="", help="폴리싱 모델 (grok/claude/claude-haiku/gemini/none)")
    parser.add_argument("--mode", default="", help="실행 모드 (scheduled=전체 활성 사이트 순회)")
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

    # 니치 파싱: 쉼표 구분 → 리스트
    cli_niches = [n.strip() for n in args.niche.split(",") if n.strip()] if args.niche else []
    if cli_niches:
        log.info(f"니치 설정: {cli_niches}")

    # ETF 리포트 파이프라인 (별도 모듈로 위임)
    if args.pipeline == "etf-report":
        from etf_report import run_etf_report
        run_etf_report(report_type="blog-ready", dry_run=args.dry_run)
        return

    # ── scheduled 모드: Supabase에서 전체 활성 사이트 조회 → 순회 발행 ──
    if args.mode == "scheduled":
        sites = _get_all_active_sites()
        if not sites:
            log.warning("활성 사이트 없음. Supabase sites 테이블을 확인하세요.")
            sys.exit(0)

        log.info(f"═══ Scheduled Mode: {len(sites)}개 활성 사이트 발행 시작 ═══")
        for site in sites:
            site_id = site.get("id", "unknown")
            domain = site.get("domain", site.get("wp_url", ""))
            log.info(f"\n▶ [{site_id}] {domain}")
            try:
                run_pipeline(
                    count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                    site_override=site, golden_mode=args.golden,
                    cli_draft_model=args.draft_model, cli_polish_model=args.polish_model,
                    niches=cli_niches,
                )
            except Exception as e:
                log.error(f"[{site_id}] 파이프라인 실패: {e}")
        log.info(f"\n═══ Scheduled Mode 완료: {len(sites)}개 사이트 처리 ═══")
        return

    # ── 특정 사이트 지정 ──
    if args.site_id:
        global SITE_ID
        SITE_ID = args.site_id
        site = _get_site_config(args.site_id)
        if site:
            run_pipeline(count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                         site_override=site, adsense_mode=args.adsense_mode, golden_mode=args.golden,
                         cli_draft_model=args.draft_model, cli_polish_model=args.polish_model,
                         niches=cli_niches)
        else:
            log.error(f"사이트 '{args.site_id}' 를 찾을 수 없습니다.")
            sys.exit(1)
        return

    # ── 단일 사이트 모드 (환경변수 기반, 레거시 호환) ──
    if not WP_URL:
        log.error("WP_URL 환경변수 없음. --site-id 또는 --mode scheduled를 사용하세요.")
        sys.exit(1)
    run_pipeline(count=args.count, dry_run=args.dry_run, pipeline=args.pipeline,
                 adsense_mode=args.adsense_mode, golden_mode=args.golden,
                 cli_draft_model=args.draft_model, cli_polish_model=args.polish_model,
                 niches=cli_niches)


if __name__ == "__main__":
    main()
