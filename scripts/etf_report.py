#!/usr/bin/env python3
"""
ETF 블로그 리포트 발행 모듈
=============================
ETF Dashboard API → 리포트 JSON fetch → AI 전문가 톤 블로그 글 생성 → WordPress 발행

사용:
  python scripts/etf_report.py                    # 일간 리포트 발행
  python scripts/etf_report.py --dry-run           # 테스트 (발행 안 함)
  python scripts/etf_report.py --report-type daily  # daily/rotation/performance/full
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 경로 설정
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etf-report")

KST = timezone(timedelta(hours=9))

# 환경변수
ETF_API_URL = os.environ.get("ETF_API_URL", "") or "https://wp-etf.up.railway.app"
ETF_REPORT_TOKEN = os.environ.get("ETF_REPORT_TOKEN", "") or "etf-wp-auto-2026-secret"
WP_URL = os.environ.get("WP_URL", "")
WP_USER = os.environ.get("WP_USERNAME", "")
WP_PASS = os.environ.get("WP_APP_PASSWORD", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")
GROK_KEY = os.environ.get("GROK_API_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
SITE_ID = os.environ.get("SITE_ID", "site-1")


# ═══════════════════════════════════════════════════════
# 1. ETF Dashboard API 연동
# ═══════════════════════════════════════════════════════

def fetch_etf_report(report_type: str = "blog-ready") -> dict:
    """ETF Dashboard에서 리포트 JSON 가져오기"""
    import requests

    endpoint_map = {
        "daily": "/api/v1/reports/daily",
        "rotation": "/api/v1/reports/rotation",
        "performance": "/api/v1/reports/performance",
        "blog-ready": "/api/v1/reports/blog-ready",
    }

    endpoint = endpoint_map.get(report_type, endpoint_map["blog-ready"])
    url = f"{ETF_API_URL}{endpoint}"

    log.info(f"ETF 리포트 가져오는 중: {url}")

    try:
        headers = {"X-Report-Token": ETF_REPORT_TOKEN} if ETF_REPORT_TOKEN else {}
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        log.info(f"리포트 수신 완료 ({len(json.dumps(data))} bytes)")
        return data
    except Exception as e:
        log.error(f"ETF 리포트 fetch 실패: {e}")
        return {}


# ═══════════════════════════════════════════════════════
# 2. ETF 리포트 전용 프롬프트
# ═══════════════════════════════════════════════════════

import random as _random

# 분석 앵글 3종 — 매일 순환
ANALYSIS_ANGLES = [
    "가치사슬(Value Chain)",
    "단기 모멘텀",
    "경쟁우위",
]


def _extract_payload(report: dict) -> dict:
    """ETF API 응답에서 프롬프트 Input Data Payload 자동 추출"""
    daily = report.get("daily", {})
    leading = daily.get("leading_sectors", [])
    featured = daily.get("featured_stocks", [])
    signals = daily.get("signals_summary", {})

    # 주도 섹터 (1위)
    top_sector = leading[0]["sector"] if leading else "미확인"

    # 타겟 핵심 종목 (주도섹터 내 상승률 1위)
    sector_stocks = [f for f in featured if f.get("sector") == top_sector]
    if not sector_stocks:
        sector_stocks = featured[:1]
    target_stock = sector_stocks[0]["stock_name"] if sector_stocks else "미확인"

    # 주요 이슈 (시장 브리핑 요약)
    briefing = daily.get("market_briefing", "데이터 없음")

    # 수급 동향 (신호 분포)
    buy_total = signals.get("buy", 0) + signals.get("strong_buy", 0)
    sell_total = signals.get("sell", 0)
    signal_details = signals.get("details", [])
    supply_parts = [f"매수 {buy_total}건 vs 매도 {sell_total}건"]
    for d in signal_details[:3]:
        supply_parts.append(f"{d['etf_name']}: {d['signal']}(신뢰도 {d['confidence']}%)")
    supply_text = " | ".join(supply_parts)

    # 앵글 — 날짜 기반 순환
    day_of_year = datetime.now(KST).timetuple().tm_yday
    angle = ANALYSIS_ANGLES[day_of_year % len(ANALYSIS_ANGLES)]

    return {
        "top_sector": top_sector,
        "target_stock": target_stock,
        "briefing": briefing,
        "supply_text": supply_text,
        "angle": angle,
    }


def build_etf_blog_prompt(report: dict) -> str:
    """ETF 리포트 JSON → 퀀트 애널리스트 프롬프트 (HTML 출력)"""
    daily = report.get("daily", {})
    rotation = report.get("rotation", {})
    performance = report.get("performance", {})

    today = daily.get("date", datetime.now(KST).strftime("%Y-%m-%d"))
    market = daily.get("market_summary", {})
    rankings = daily.get("sector_rankings", [])
    signals = daily.get("signals_summary", {})
    featured = daily.get("featured_stocks", [])
    leading = daily.get("leading_sectors", [])
    freq_top5 = rotation.get("frequency_top5", [])
    cycle = rotation.get("rotation_cycle", {})
    perf_summary = performance.get("summary", {})
    active_positions = performance.get("active_positions", [])

    # Input Data Payload 자동 추출
    payload = _extract_payload(report)

    # === 데이터 블록 구성 ===

    ranking_text = ""
    for r in rankings[:10]:
        ranking_text += (
            f"  {r['rank']}위 {r['sector']} ({r['grade']}등급): "
            f"{r['change_rate']:+.2f}%, 주도점수 {r['leadership_score']}, "
            f"상승비율 {r['breadth_ratio']:.0f}%"
            f"{' ★주도섹터' if r.get('is_leading') else ''}\n"
        )

    leading_text = ""
    for s in leading:
        leading_text += (
            f"  - {s['sector']} ({s['etf_name']}): "
            f"{s['change_rate']:+.2f}%, 점수 {s['leadership_score']}\n"
        )

    buy_total = signals.get("buy", 0) + signals.get("strong_buy", 0)
    signal_text = (
        f"  매수 신호: {buy_total}건 (적극매수 {signals.get('strong_buy', 0)} + 매수 {signals.get('buy', 0)})\n"
        f"  매도 신호: {signals.get('sell', 0)}건\n"
        f"  관망: {signals.get('hold', 0)}건\n"
    )
    for d in signals.get("details", []):
        signal_text += f"  → {d['etf_name']}: {d['signal']} (신뢰도 {d['confidence']}%)\n"

    featured_text = ""
    for f in featured[:6]:
        featured_text += (
            f"  - [{f['sector']}] {f['stock_name']}: {f['change_rate']:+.2f}% (비중 {f['weight']:.1f}%)\n"
        )

    rotation_text = f"  평균 TOP3 유지일수: {cycle.get('avg_cycle_days', 0)}일\n"
    for ft in freq_top5:
        rotation_text += (
            f"  {ft['rank']}위 {ft['sector']}: "
            f"{ft['entry_count']}회 등장, 총 {ft['total_days']}일, "
            f"평균수익 {ft['avg_peak_return']:+.1f}%\n"
        )

    perf_text = (
        f"  활성 추적: {perf_summary.get('active_count', 0)}건\n"
        f"  평균 수익률: {perf_summary.get('avg_return', 0):+.2f}%\n"
        f"  승률: {perf_summary.get('win_rate', 0):.0f}%\n"
    )
    for p in active_positions[:5]:
        perf_text += (
            f"  → {p['etf_name']} ({p['sector']}): "
            f"누적 {p['cumulative_return_pct']:+.2f}%, {p['consecutive_days']}일째\n"
        )

    prompt = f"""# Role & Persona (역할 및 페르소나)
당신은 데이터를 기반으로 시장의 이면을 꿰뚫어 보는 상위 0.1% 퀀트 애널리스트이자 산업 분석 전문가입니다.
당신의 어조는 단호하고 냉철하며(~하십시오, ~입니다), 독자에게 압도적인 통찰력을 제공해야 합니다.
* 절대 과거 데이터의 단순 평균치를 내거나 위키백과식으로 정보를 나열하지 마십시오.
* 화자의 정체성은 항상 '냉철한 데이터 분석가'로 고정하되, 글의 초점은 [{payload['angle']}]에 맞춰 전개하십시오.

# Input Data Payload (실시간 주입 데이터 — {today})
- 당일 주도 섹터: {payload['top_sector']}
- 타겟 핵심 종목: {payload['target_stock']}
- 주요 이슈: {payload['briefing']}
- 수급 동향: {payload['supply_text']}
- 오늘의 분석 앵글: {payload['angle']}

# Raw Market Data (원본 데이터)
### 시장 지수
  KOSPI: {market.get('kospi', {}).get('price', 0):,.0f} ({market.get('kospi', {}).get('change_rate', 0):+.2f}%)
  KOSDAQ: {market.get('kosdaq', {}).get('price', 0):,.0f} ({market.get('kosdaq', {}).get('change_rate', 0):+.2f}%)

### 섹터 순위 (전체)
{ranking_text}

### 주도섹터 TOP3
{leading_text}

### 종합 신호 분포
{signal_text}

### 오늘의 특징주
{featured_text}

### 섹터 순환 분석 (최근 90일)
{rotation_text}

### TOP3 수익률 추적
{perf_text}

# Core Analysis Logic (핵심 분석 지시사항)
주입된 데이터를 바탕으로 다음의 논리적 흐름에 따라 분석을 수행하십시오.

1. 병목 요소와 가격 결정권 (Moat & Pricing Power):
   - 해당 산업 밸류체인 내에서 가장 치명적인 '병목(Bottleneck) 분야'가 무엇인지 정의하십시오.
   - 타겟 종목({payload['target_stock']})이 이 병목을 쥐고 흔들 수 있는 '가격 결정권'이 있는지 분석하십시오.
   - 가격 결정권이 영업이익률(OPM)의 폭발적 증가로 이어질 가능성이 크다면, 이를 강력하게 어필하십시오.

2. 멀티팩터 모멘텀 스코어링 (Multi-factor Scoring):
   - [단기 모멘텀 점수]: 주입된 '이슈'와 '수급' 데이터를 중심으로 평가 (1~10점 산정 및 이유 서술).
   - [중기 모멘텀 점수]: 산업의 구조적 성장성, 기술적 해자(Technical Moat), 주요 경쟁사와의 스펙/점유율 비교를 통한 우위 관점에서 평가 (1~10점 산정 및 이유 서술).

# Output Structure (출력 포맷 — HTML, 100% 준수)
반드시 HTML 형식으로 다음 구조를 순서대로 출력하십시오.

<h2>[{today}] [주도 섹터/종목에 대한 통찰을 담은 도발적인 제목]</h2>

<p>(도입부) 주입된 주도 섹터와 주요 이슈를 엮어, 왜 오늘 이 종목을 봐야만 하는지 직관적인 팩트로 훅(Hook)을 날리십시오. 3~4문장.</p>

<div class="key-point"><strong>이 글의 순서</strong><br/>
<ol>
<li>[산업 병목]이 만든 구조적 결핍</li>
<li>{payload['target_stock']}의 가격 결정권과 밸류체인 장악력</li>
<li>퀀트 스코어링: 단기 수급 vs 중기 해자</li>
</ol></div>

<h2>1. 밸류체인의 병목(Bottleneck), 누가 쥐고 있는가?</h2>
<p>(분석 지시사항 1번을 바탕으로 해당 산업의 병목 현상과 경쟁 환경을 서술. 500~700자.)</p>
<table>(병목 분야 비교표: 분야 / 진입장벽 / 가격결정권 / 관련 종목)</table>

<h2>2. {payload['target_stock']} : 가격 결정권이 만드는 영업이익률의 마법</h2>
<p>(타겟 종목이 어떻게 병목을 해결하고 영업이익을 펌핑할 수 있는지 분석. 500~700자.)</p>

<div class="tip-box"><strong>투자 밸류에이션 팁</strong><br/>
(경쟁사 비교 관점에서 이 종목이 현재 저평가인지 고평가인지 핵심 1줄 코멘트)</div>

<h2>3. 입체적 모멘텀 스코어링 (단기 vs 중기)</h2>
<p>(분석 지시사항 2번을 바탕으로 논리적 점수 산출)</p>
<table>(단기 모멘텀 / 중기 모멘텀 비교표: 항목 / 점수 / 근거)</table>

<blockquote><strong>애널리스트 팩트 체크</strong><br/>
(분석 내용을 뒷받침하는 가장 결정적인 투자 지표나 수치 1개 강조)</blockquote>

<div class="key-point"><strong>최종 투자 요약 (Executive Summary)</strong><br/>
(전체 분석을 3문장으로 압축하고, 독자가 취해야 할 명확한 액션 플랜을 제시)</div>

<p><em>본 리포트는 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.</em></p>

=== HTML 규칙 (절대 준수) ===
- <h1> 금지 (워드프레스 자동 생성)
- <h2>, <h3>, <p>, <strong>, <ol>/<ul>, <table>, <blockquote> 사용
- <div class="tip-box">, <div class="key-point"> 사용 가능
- <table>은 반드시 <thead><tr><th>헤더</th></tr></thead><tbody><tr><td>내용</td></tr></tbody> 구조
- 마크다운 문법 절대 금지 — HTML 태그만 사용
- <strong> 강조 최소 8개
- 분량: 2,000~3,500자 (데이터 밀도 높게)
- 주입된 데이터의 수치만 인용. 존재하지 않는 통계/기관명 날조 절대 금지.
"""
    return prompt


# ═══════════════════════════════════════════════════════
# 3. AI 글 생성 (기존 ContentGenerator 재활용)
# ═══════════════════════════════════════════════════════

def generate_blog_content(prompt: str) -> tuple:
    """AI로 블로그 글 생성 — Grok → Gemini → DeepSeek 폴체인 + Claude 폴리싱"""
    import requests

    content = None
    model_used = None

    # 1순위: Grok
    if GROK_KEY and not content:
        try:
            log.info("Grok으로 ETF 리포트 생성 중...")
            resp = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "grok-3-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 5000,
                },
                timeout=180,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            model_used = "grok-3-mini"
            log.info(f"Grok 생성 완료 ({len(content)}자)")
        except Exception as e:
            log.warning(f"Grok 실패: {e}")

    # 2순위: Gemini
    if GEMINI_KEY and not content:
        try:
            log.info("Gemini로 ETF 리포트 생성 중...")
            resp = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 5000},
                },
                timeout=180,
            )
            resp.raise_for_status()
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            model_used = "gemini-2.0-flash"
            log.info(f"Gemini 생성 완료 ({len(content)}자)")
        except Exception as e:
            log.warning(f"Gemini 실패: {e}")

    # 3순위: DeepSeek
    if DEEPSEEK_KEY and not content:
        try:
            log.info("DeepSeek로 ETF 리포트 생성 중...")
            resp = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 5000,
                },
                timeout=180,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            model_used = "deepseek-chat"
            log.info(f"DeepSeek 생성 완료 ({len(content)}자)")
        except Exception as e:
            log.warning(f"DeepSeek 실패: {e}")

    if not content:
        log.error("모든 AI 모델 실패")
        return None, None

    # Claude 폴리싱 (선택)
    if CLAUDE_KEY:
        try:
            polish_prompt = f"""아래 ETF 시장 분석 블로그 글을 다듬어주세요.
규칙:
- 어색한 표현 수정, 문단 흐름 개선
- 데이터 정확성 유지 (수치 변경 금지)
- HTML 구조 유지
- 1,500~2,500자 유지
- 면책 문구 유지

원문:
{content}"""
            log.info("Claude 폴리싱 중...")
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": CLAUDE_KEY,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 6000,
                    "messages": [{"role": "user", "content": polish_prompt}],
                },
                timeout=180,
            )
            resp.raise_for_status()
            polished = resp.json()["content"][0]["text"]
            log.info(f"폴리싱 완료 ({len(polished)}자)")
            return polished, model_used + "+claude"
        except Exception as e:
            log.warning(f"Claude 폴리싱 실패 (원문 사용): {e}")

    return content, model_used


# ═══════════════════════════════════════════════════════
# 4. 제목 추출
# ═══════════════════════════════════════════════════════

def extract_title(content: str) -> tuple:
    """HTML에서 첫 h2 태그를 제목으로 추출"""
    import re

    match = re.search(r"<h2[^>]*>(.*?)</h2>", content, re.DOTALL)
    if match:
        title = re.sub(r"<[^>]+>", "", match.group(1)).strip()
        content = content[: match.start()] + content[match.end() :]
        return title, content.strip()

    # h2가 없으면 첫 줄을 제목으로
    lines = content.strip().split("\n")
    title = re.sub(r"<[^>]+>", "", lines[0]).strip()[:100]
    return title, "\n".join(lines[1:]).strip()


# ═══════════════════════════════════════════════════════
# 5. WordPress 발행
# ═══════════════════════════════════════════════════════

def publish_to_wordpress(title: str, content: str, category: str = "ETF 시장분석") -> dict:
    """WordPress REST API로 발행"""
    import base64
    import requests

    url = WP_URL.rstrip("/")
    if url.endswith("/wp-json/wp/v2"):
        url = url[: -len("/wp-json/wp/v2")]

    cred = base64.b64encode(f"{WP_USER}:{WP_PASS}".encode()).decode()
    headers = {
        "Authorization": f"Basic {cred}",
        "Content-Type": "application/json",
    }

    # 카테고리 조회/생성
    cat_id = None
    try:
        resp = requests.get(
            f"{url}/wp-json/wp/v2/categories",
            headers=headers,
            params={"search": category, "per_page": 5},
            timeout=10,
        )
        cats = resp.json()
        for c in cats:
            import html as _html
            if _html.unescape(c["name"]).lower() == category.lower():
                cat_id = c["id"]
                break
        if not cat_id:
            resp = requests.post(
                f"{url}/wp-json/wp/v2/categories",
                headers=headers,
                json={"name": category},
                timeout=10,
            )
            cat_id = resp.json().get("id")
    except Exception as e:
        log.warning(f"카테고리 처리 실패: {e}")

    today = datetime.now(KST).strftime("%Y-%m-%d")
    post_data = {
        "title": title,
        "content": content,
        "status": "publish",
        "categories": [cat_id] if cat_id else [],
        "tags": [],
        "meta": {
            "rank_math_focus_keyword": f"ETF 시장분석 {today}",
            "rank_math_title": f"{title} | PlanX AI",
            "rank_math_description": f"{today} ETF 섹터 순위, 주도섹터, 시장 신호 종합 분석 리포트",
        },
    }

    try:
        resp = requests.post(
            f"{url}/wp-json/wp/v2/posts",
            headers=headers,
            json=post_data,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "status": "published",
            "id": data["id"],
            "url": data.get("link", ""),
            "title": data.get("title", {}).get("rendered", title),
        }
    except Exception as e:
        log.error(f"WordPress 발행 실패: {e}")
        return {"status": "failed", "error": str(e)}


# ═══════════════════════════════════════════════════════
# 6. Supabase 로깅
# ═══════════════════════════════════════════════════════

def log_to_supabase(result: dict, model_used: str, report_type: str,
                    content_length: int = 0, quality_score: float = 0):
    """발행 결과를 Supabase에 기록 (실제 메트릭 포함)"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        return

    import requests

    try:
        requests.post(
            f"{SUPABASE_URL}/rest/v1/publish_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json={
                "site_id": SITE_ID,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "keyword": f"etf-report-{report_type}",
                "pipeline": "etf-report",
                "status": result.get("status", "unknown"),
                "quality_score": quality_score,
                "content_length": content_length,
                "has_image": False,
                "created_at": datetime.now(KST).isoformat(),
            },
            timeout=10,
        )
        log.info(f"Supabase 로깅 완료 (품질: {quality_score}, 길이: {content_length}자)")
    except Exception as e:
        log.warning(f"Supabase 로깅 실패 (무시): {e}")


# ═══════════════════════════════════════════════════════
# 6-B. SNS 알림 (Telegram / Discord)
# ═══════════════════════════════════════════════════════

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def notify_sns(title: str, url: str, quality_score: float):
    """ETF 리포트 발행 알림 (Telegram + Discord)"""
    import requests

    today = datetime.now(KST).strftime("%Y-%m-%d")
    message = f"📊 ETF 리포트 발행 ({today})\n\n{title}\n품질: {quality_score}/100\n{url}"

    # Telegram
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        try:
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"},
                timeout=10,
            )
            log.info("Telegram 알림 전송 완료")
        except Exception as e:
            log.warning(f"Telegram 알림 실패: {e}")

    # Discord
    if DISCORD_WEBHOOK:
        try:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": message},
                timeout=10,
            )
            log.info("Discord 알림 전송 완료")
        except Exception as e:
            log.warning(f"Discord 알림 실패: {e}")


# ═══════════════════════════════════════════════════════
# 7. 메인 파이프라인
# ═══════════════════════════════════════════════════════

def _simple_quality_check(content: str) -> float:
    """ETF 리포트용 간이 품질 점수 (100점 만점)"""
    import re
    score = 0

    plain = re.sub(r'<[^>]+>', '', content)
    length = len(plain)

    # 길이 (25점): 2000자+ = 25, 1500+ = 20, 1000+ = 10
    if length >= 2000: score += 25
    elif length >= 1500: score += 20
    elif length >= 1000: score += 10

    # H2 소제목 (20점): 3~5개 = 20
    h2_count = len(re.findall(r'<h2', content, re.IGNORECASE))
    if 3 <= h2_count <= 5: score += 20
    elif h2_count >= 2: score += 12

    # 테이블 (15점)
    if '<table' in content: score += 15

    # 비주얼 블록 (15점)
    visual = 0
    if '<blockquote' in content: visual += 1
    if 'tip-box' in content: visual += 1
    if 'key-point' in content: visual += 1
    if visual >= 2: score += 15
    elif visual >= 1: score += 8

    # strong 강조 (10점)
    strong_count = len(re.findall(r'<strong', content, re.IGNORECASE))
    if strong_count >= 8: score += 10
    elif strong_count >= 4: score += 6

    # 면책 문구 (5점)
    if '투자 참고용' in content or '투자 판단의 책임' in content: score += 5

    # HTML 구조 (10점)
    if '<h2' in content and '<p' in content and '</p>' in content: score += 10

    return score


def run_etf_report(report_type: str = "blog-ready", dry_run: bool = False):
    """ETF 리포트 파이프라인 실행"""
    log.info("=" * 60)
    log.info(f"ETF Report Pipeline — {report_type} (퀀트 전략)")
    log.info(f"  API: {ETF_API_URL}")
    log.info(f"  WP: {WP_URL}")
    log.info(f"  Dry Run: {dry_run}")
    log.info("=" * 60)

    # Step 1: ETF Dashboard에서 리포트 fetch
    report = fetch_etf_report(report_type)
    if not report:
        log.error("리포트 데이터 없음 — 종료")
        return

    # blog-ready가 아닌 경우 daily를 기본으로 래핑
    if report_type != "blog-ready" and "daily" not in report:
        report = {"daily": report, "rotation": {}, "performance": {}}

    # API 응답 검증 — daily 데이터 필수 필드 체크
    daily = report.get("daily", {})
    if not daily.get("sector_rankings") and not daily.get("leading_sectors"):
        log.error("ETF API 응답에 섹터 데이터 없음 — 발행 중단")
        return

    # Step 2: AI 프롬프트 생성 + 글 생성
    prompt = build_etf_blog_prompt(report)
    content, model_used = generate_blog_content(prompt)
    if not content:
        log.error("AI 글 생성 실패 — 종료")
        return

    # Step 2.5: 프리미엄 스타일링 (main.py ContentFormatter 활용)
    try:
        from main import ContentFormatter
        cf = ContentFormatter()
        # ETF 리포트 전용 금융 테마 색상 적용
        cf.H2_STYLE = (
            'style="font-size:23px;font-weight:800;color:#0f172a;'
            'margin:48px 0 20px;padding:16px 0 12px;'
            'border-bottom:3px solid #1e40af"'
        )
        cf.H3_STYLE = (
            'style="font-size:18px;font-weight:700;color:#1e293b;'
            'margin:28px 0 12px;padding-left:12px;'
            'border-left:4px solid #1e40af"'
        )
        cf.THEAD_STYLE = 'style="background:linear-gradient(135deg,#1e3a5f,#1e40af)"'
        cf.TIP_BOX_STYLE = (
            'style="background:linear-gradient(135deg,#eff6ff,#dbeafe);'
            'border:1px solid #60a5fa;border-radius:12px;padding:20px 24px;margin:28px 0"'
        )
        cf.TIP_BOX_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
            '<span style="font-size:20px">\U0001f4b0</span>'
            '<span style="font-weight:700;color:#1e40af;font-size:14px;letter-spacing:0.5px">'
            '\ud22c\uc790 \ud301</span></div>'
        )
        cf.KEY_POINT_STYLE = (
            'style="background:linear-gradient(135deg,#fefce8,#fef9c3);'
            'border-left:4px solid #ca8a04;'
            'border-radius:0 12px 12px 0;padding:18px 24px;margin:28px 0"'
        )
        cf.KEY_POINT_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">'
            '<span style="font-size:18px">\U0001f3af</span>'
            '<span style="font-weight:700;color:#a16207;font-size:14px;letter-spacing:0.5px">'
            '\ud575\uc2ec \ud3ec\uc778\ud2b8</span></div>'
        )
        cf.BLOCKQUOTE_STYLE = (
            'style="background:linear-gradient(135deg,#f0fdf4,#dcfce7);'
            'border-left:4px solid #16a34a;border-radius:0 12px 12px 0;'
            'padding:20px 24px;margin:28px 0;font-style:normal;color:#166534"'
        )
        cf.BLOCKQUOTE_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
            '<span style="font-size:18px">\U0001f4ca</span>'
            '<span style="font-weight:700;color:#166534;font-size:14px;letter-spacing:0.5px">'
            '\uc560\ub110\ub9ac\uc2a4\ud2b8 \ud329\ud2b8\uccb4\ud06c</span></div>'
        )
        cf.CTA_BOX = (
            '\n<div style="background:linear-gradient(135deg,#1e3a5f,#1e40af);'
            'border-radius:16px;padding:28px 32px;margin:40px 0;text-align:center;'
            'box-shadow:0 8px 32px rgba(30,64,175,0.25)">\n'
            '<p style="color:#fff;font-size:18px;font-weight:700;margin:0 0 8px">'
            '\U0001f4c8 \ub370\uc774\ud130 \uae30\ubc18 \ud22c\uc790 \uc778\uc0ac\uc774\ud2b8</p>\n'
            '<p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px;line-height:1.6">'
            '\ubcf8 \ub9ac\ud3ec\ud2b8\ub294 \ud22c\uc790 \ucc38\uace0\uc6a9\uc774\uba70, \ud22c\uc790 \ud310\ub2e8\uc758 \ucc45\uc784\uc740 \ubcf8\uc778\uc5d0\uac8c \uc788\uc2b5\ub2c8\ub2e4.</p>\n'
            '</div>\n'
        )
        content = cf.format(content, keyword="ETF 시장분석", category="finance-invest")
        log.info("프리미엄 스타일링 적용 완료")
    except Exception as e:
        log.warning(f"스타일링 실패 (원문 유지): {e}")

    # Step 3: 제목 추출
    title, content = extract_title(content)
    import re
    content_length = len(re.sub(r'<[^>]+>', '', content))
    log.info(f"제목: {title}")
    log.info(f"본문: {content_length}자 ({model_used})")

    # Step 3.5: 품질 검증
    quality_score = _simple_quality_check(content)
    log.info(f"품질 점수: {quality_score}/100")

    if quality_score < 50:
        log.warning(f"품질 극히 미달 ({quality_score}/100) — 발행 중단")
        return

    # Step 4: 발행
    if dry_run:
        log.info("[DRY RUN] 발행 스킵")
        log.info(f"제목: {title}")
        log.info(f"품질: {quality_score}/100, 길이: {content_length}자")
        log.info(f"본문 미리보기:\n{content[:500]}...")
        return

    if not WP_URL or not WP_USER or not WP_PASS:
        log.error("WordPress 인증 정보 없음 (WP_URL, WP_USERNAME, WP_APP_PASSWORD)")
        return

    result = publish_to_wordpress(title, content)

    if result["status"] == "published":
        log.info(f"발행 성공: {result.get('url', '')}")
        log_to_supabase(result, model_used, report_type,
                        content_length=content_length, quality_score=quality_score)
        # SNS 알림
        notify_sns(title, result.get("url", ""), quality_score)
    else:
        log.error(f"발행 실패: {result.get('error', '')}")
        log_to_supabase(result, model_used, report_type,
                        content_length=content_length, quality_score=quality_score)

    log.info("=" * 60)
    log.info("ETF Report Pipeline 완료")
    log.info("=" * 60)


# ═══════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="ETF Blog Report Publisher")
    parser.add_argument(
        "--report-type",
        default="blog-ready",
        choices=["daily", "rotation", "performance", "blog-ready"],
        help="리포트 유형",
    )
    parser.add_argument("--dry-run", action="store_true", help="발행 없이 테스트")
    parser.add_argument("--etf-api-url", default="", help="ETF Dashboard API URL 오버라이드")
    args = parser.parse_args()

    if args.etf_api_url:
        global ETF_API_URL
        ETF_API_URL = args.etf_api_url

    run_etf_report(report_type=args.report_type, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
