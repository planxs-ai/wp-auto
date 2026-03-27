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
import re as _re


# ═══════════════════════════════════════════════════════
# 2-A. 인라인 SVG 차트 생성
# ═══════════════════════════════════════════════════════

def _build_sector_chart_html(rankings: list) -> str:
    """섹터 등락률 수평 바 차트 (순수 HTML/CSS — WordPress 호환)"""
    top = rankings[:10]
    if not top:
        return ""

    max_abs = max(abs(r.get("change_rate", 0)) for r in top) or 1

    # 등급별 뱃지 색상
    grade_colors = {
        "S": ("#fbbf24", "#92400e"), "A": ("#34d399", "#065f46"),
        "B": ("#60a5fa", "#1e40af"), "C": ("#a78bfa", "#5b21b6"),
        "D": ("#f87171", "#991b1b"),
    }

    rows = []
    for r in top:
        rate = r.get("change_rate", 0)
        sector = r.get("sector", "")
        grade = r.get("grade", "")
        is_leading = r.get("is_leading", False)
        bar_pct = min(abs(rate) / max_abs * 100, 100)

        bar_color = "#16a34a" if rate >= 0 else "#ef4444"
        bar_bg = "#dcfce7" if rate >= 0 else "#fee2e2"
        rate_color = "#15803d" if rate >= 0 else "#dc2626"
        g_bg, g_fg = grade_colors.get(grade, ("#e2e8f0", "#475569"))
        star = ' <span style="color:#f59e0b;font-size:14px">&#9733;</span>' if is_leading else ""

        rows.append(
            f'<div style="display:flex;align-items:center;gap:10px;padding:8px 0;'
            f'border-bottom:1px solid #f1f5f9">'
            # 섹터명
            f'<div style="width:80px;flex-shrink:0;font-weight:600;font-size:14px;color:#1e293b">'
            f'{sector}{star}</div>'
            # 등급 뱃지
            f'<div style="width:32px;flex-shrink:0;text-align:center">'
            f'<span style="background:{g_bg};color:{g_fg};font-size:11px;font-weight:800;'
            f'padding:2px 6px;border-radius:4px">{grade}</span></div>'
            # 바 차트
            f'<div style="flex:1;background:{bar_bg};border-radius:6px;height:22px;position:relative;overflow:hidden">'
            f'<div style="width:{bar_pct:.0f}%;height:100%;background:{bar_color};border-radius:6px;'
            f'opacity:0.8;transition:width 0.3s"></div></div>'
            # 등락률
            f'<div style="width:65px;flex-shrink:0;text-align:right;font-weight:800;'
            f'font-size:14px;color:{rate_color}">{rate:+.2f}%</div>'
            f'</div>'
        )

    return (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;'
        f'padding:20px 24px;margin:28px 0">'
        f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:14px">'
        f'<span style="font-size:20px">&#128200;</span>'
        f'<span style="font-weight:800;color:#0f172a;font-size:16px">'
        f'\uc139\ud130 \ub4f1\ub77d\ub960 TOP 10</span>'
        f'<span style="font-size:11px;color:#94a3b8;margin-left:auto">&#9733; = \uc8fc\ub3c4\uc139\ud130</span></div>'
        f'{"".join(rows)}'
        f'</div>'
    )


def _build_signal_badge_html(signals: dict) -> str:
    """매수/매도/관망 신호 카드 HTML"""
    buy = signals.get("buy", 0) + signals.get("strong_buy", 0)
    sell = signals.get("sell", 0)
    hold = signals.get("hold", 0)
    details = signals.get("details", [])

    badges = (
        f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:20px 0">'
        f'<div style="flex:1;min-width:100px;background:#f0fdf4;border:1px solid #bbf7d0;'
        f'border-radius:12px;padding:14px 18px;text-align:center">'
        f'<div style="font-size:28px;font-weight:900;color:#16a34a">{buy}</div>'
        f'<div style="font-size:12px;color:#166534;font-weight:600">매수 신호</div></div>'
        f'<div style="flex:1;min-width:100px;background:#fef2f2;border:1px solid #fecaca;'
        f'border-radius:12px;padding:14px 18px;text-align:center">'
        f'<div style="font-size:28px;font-weight:900;color:#dc2626">{sell}</div>'
        f'<div style="font-size:12px;color:#991b1b;font-weight:600">매도 신호</div></div>'
        f'<div style="flex:1;min-width:100px;background:#f8fafc;border:1px solid #e2e8f0;'
        f'border-radius:12px;padding:14px 18px;text-align:center">'
        f'<div style="font-size:28px;font-weight:900;color:#64748b">{hold}</div>'
        f'<div style="font-size:12px;color:#475569;font-weight:600">관망</div></div>'
        f'</div>'
    )

    if details:
        detail_rows = ""
        for d in details[:5]:
            is_buy = "매수" in d.get("signal", "")
            sig_bg = "#f0fdf4" if is_buy else "#fef2f2"
            sig_color = "#16a34a" if is_buy else "#dc2626"
            conf = d.get("confidence", 0)
            conf_bar_color = "#16a34a" if conf >= 70 else "#f59e0b" if conf >= 50 else "#ef4444"
            detail_rows += (
                f'<div style="display:flex;align-items:center;gap:12px;padding:10px 14px;'
                f'border-bottom:1px solid #f1f5f9">'
                f'<span style="font-weight:700;font-size:14px;color:#0f172a;flex:1">{d["etf_name"]}</span>'
                f'<span style="background:{sig_bg};color:{sig_color};padding:4px 12px;border-radius:6px;'
                f'font-weight:700;font-size:13px">{d["signal"]}</span>'
                f'<div style="width:60px;background:#e2e8f0;border-radius:4px;height:8px;overflow:hidden">'
                f'<div style="width:{conf}%;height:100%;background:{conf_bar_color};border-radius:4px"></div></div>'
                f'<span style="font-size:12px;color:#64748b;width:36px;text-align:right">{conf}%</span>'
                f'</div>'
            )
        badges += (
            f'<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;'
            f'overflow:hidden;margin:12px 0">{detail_rows}</div>'
        )

    return badges


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

    # 시장 지수 요약 (프롬프트 내 삽입용)
    kospi = market.get('kospi', {})
    kosdaq = market.get('kosdaq', {})
    market_summary = (
        f"KOSPI {kospi.get('price', 0):,.0f} ({kospi.get('change_rate', 0):+.2f}%) / "
        f"KOSDAQ {kosdaq.get('price', 0):,.0f} ({kosdaq.get('change_rate', 0):+.2f}%)"
    )

    prompt = f"""# Role & Persona
당신은 데이터를 기반으로 시장의 이면을 꿰뚫어 보는 상위 0.1% 퀀트 애널리스트입니다.
어조: 단호하고 냉철하며 (~하십시오, ~입니다), 압도적인 통찰력 제공.
* 위키백과식 정보 나열 금지. 모든 문장에 '그래서 투자자가 뭘 해야 하는지'를 녹이십시오.
* 분석 앵글: [{payload['angle']}]

# 구독자가 원하는 핵심 3가지 (반드시 전달)
1. **오늘 돈이 몰리는 곳은 어디인가?** → 주도섹터 + 매수신호 종목
2. **왜 그 곳에 돈이 몰리는가?** → 병목/수급/모멘텀 근거
3. **나는 지금 뭘 해야 하는가?** → 구체적 액션 (매수/관망/비중조절)

# 실시간 데이터 ({today})
시장: {market_summary}
주도섹터: {payload['top_sector']}
핵심종목: {payload['target_stock']}
수급: {payload['supply_text']}
이슈: {payload['briefing']}

### 섹터 순위 TOP10
{ranking_text}

### 주도섹터
{leading_text}

### 신호 분포
{signal_text}

### 특징주
{featured_text}

### 순환 분석 (90일)
{rotation_text}

### 수익률 추적
{perf_text}

# Output Structure (HTML — 100% 준수, 번호 순서대로)

<h2>[{today}] [주도섹터와 핵심종목을 포함한 강렬한 제목]</h2>

<div class="key-point"><strong>30초 핵심 요약</strong><br/>
<ul>
<li><strong>오늘의 주도섹터:</strong> [섹터명] — [등급] 등급, [등락률]%</li>
<li><strong>핵심 매수 신호:</strong> [ETF명] (신뢰도 [X]%)</li>
<li><strong>액션:</strong> [구체적 1줄 행동 지침]</li>
</ul></div>

<p>(도입부 — 오늘 시장에서 가장 중요한 움직임 1가지를 팩트로 훅. KOSPI/KOSDAQ 지수 포함. 3~4문장.)</p>

<h2>1. 오늘 돈은 어디로 흘러갔는가?</h2>
<p>(주도섹터 분석. 왜 이 섹터가 강세인지 수급 근거와 등급 기반으로 서술. 400~500자.)</p>
<table>
<thead><tr><th style="width:15%">섹터</th><th style="width:10%">등급</th><th style="width:15%">등락률</th><th style="width:60%">주도 근거</th></tr></thead>
<tbody>(주도섹터 TOP3 데이터 행)</tbody>
</table>

<h2>2. {payload['target_stock']} — 밸류체인 병목의 수혜자</h2>
<p>(타겟 종목이 산업 내에서 어떤 위치에 있고, 가격 결정권이 있는지 분석. 400~500자.)</p>

<div class="tip-box"><strong>밸류에이션 체크</strong><br/>
(이 종목이 현재 고평가/적정/저평가인지 핵심 1줄 + 근거 수치 1개)</div>

<h2>3. 퀀트 모멘텀 스코어링</h2>
<p>(단기 수급 + 중기 해자 관점에서 점수 산출. 각 점수의 근거를 1~2문장으로.)</p>
<table>
<thead><tr><th style="width:25%">팩터</th><th style="width:12%">점수</th><th style="width:63%">근거</th></tr></thead>
<tbody>
<tr><td><strong>단기 모멘텀</strong> (수급/이슈)</td><td>[X]/10</td><td>(근거)</td></tr>
<tr><td><strong>중기 모멘텀</strong> (성장/해자)</td><td>[X]/10</td><td>(근거)</td></tr>
<tr><td><strong>종합 점수</strong></td><td>[X]/10</td><td>(종합 판단 1줄)</td></tr>
</tbody>
</table>

<h2>4. 매매 신호 & 리스크 체크</h2>
<p>(오늘의 매수/매도 신호 분포와 주의 사항. 200~300자.)</p>

<blockquote><strong>리스크 경고</strong><br/>
(이 섹터/종목의 가장 큰 하방 리스크 1가지를 명확히 경고)</blockquote>

<div class="key-point"><strong>오늘의 액션 플랜</strong><br/>
<ol>
<li><strong>[매수/비중확대/관망 중 택1]:</strong> [구체적 ETF/종목명] — [근거 1줄]</li>
<li><strong>리스크 관리:</strong> [손절/비중조절 기준 1줄]</li>
<li><strong>내일 주시 포인트:</strong> [모니터링 대상 1줄]</li>
</ol></div>

<p style="font-size:13px;color:#94a3b8;margin-top:32px"><em>본 리포트는 투자 참고용이며, 투자 판단의 책임은 본인에게 있습니다.</em></p>

=== HTML 규칙 (절대 준수) ===
- <h1> 금지. <h2>로 시작.
- <table>: 반드시 <thead>/<tbody> 구조. <th>에 style="width:XX%" 포함.
- <div class="tip-box">, <div class="key-point"> 활용.
- <strong> 강조 최소 10개 — 구독자가 스캔할 때 눈에 들어오도록.
- 마크다운 금지. HTML 태그만.
- 분량: 2,500~4,000자.
- 주입된 데이터 수치만 인용. 가짜 통계/기관명 날조 절대 금지.
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

def _get_or_create_tags(base_url: str, headers: dict, tag_names: list) -> list:
    """태그 이름 목록 → WordPress 태그 ID 목록 (없으면 생성)"""
    import requests
    tag_ids = []
    for name in tag_names[:8]:
        try:
            resp = requests.get(
                f"{base_url}/wp-json/wp/v2/tags",
                headers=headers,
                params={"search": name, "per_page": 5},
                timeout=10,
            )
            tags = resp.json()
            found = None
            for t in tags:
                import html as _html
                if _html.unescape(t["name"]).lower() == name.lower():
                    found = t["id"]
                    break
            if not found:
                resp = requests.post(
                    f"{base_url}/wp-json/wp/v2/tags",
                    headers=headers,
                    json={"name": name},
                    timeout=10,
                )
                found = resp.json().get("id")
            if found:
                tag_ids.append(found)
        except Exception:
            pass
    return tag_ids


def publish_to_wordpress(title: str, content: str, category: str = "ETF 시장분석",
                         leading_sectors: list = None, target_stock: str = "") -> dict:
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

    # 태그 생성: 고정 + 주도섹터 + 핵심종목
    tag_names = ["ETF", "ETF 시장분석", "섹터분석"]
    if leading_sectors:
        for s in leading_sectors[:3]:
            tag_names.append(s.get("sector", ""))
    if target_stock:
        tag_names.append(target_stock)
    tag_names = [t for t in tag_names if t]
    tag_ids = _get_or_create_tags(url, headers, tag_names)

    post_data = {
        "title": title,
        "content": content,
        "status": "publish",
        "categories": [cat_id] if cat_id else [],
        "tags": tag_ids,
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

    # Step 2.5: 차트 + 신호 뱃지 삽입
    daily_data = report.get("daily", {})
    chart_svg = _build_sector_chart_html(daily_data.get("sector_rankings", []))
    signal_badges = _build_signal_badge_html(daily_data.get("signals_summary", {}))

    # 첫 번째 <h2> 뒤에 차트 삽입 (도입부 다음)
    if chart_svg:
        h2_positions = [m.end() for m in _re.finditer(r'</h2>', content)]
        if len(h2_positions) >= 2:
            # 두 번째 h2 (섹션 1) 앞에 차트 삽입
            insert_pos = h2_positions[0]
            chart_block = f'\n{chart_svg}\n'
            content = content[:insert_pos] + chart_block + content[insert_pos:]

    # 섹션 4 (매매 신호) 뒤에 뱃지 삽입
    if signal_badges:
        sig_match = _re.search(r'(<h2[^>]*>4\..*?</h2>)', content)
        if sig_match:
            insert_pos = sig_match.end()
            content = content[:insert_pos] + f'\n{signal_badges}\n' + content[insert_pos:]

    # Step 2.7: 프리미엄 스타일링 (main.py ContentFormatter)
    try:
        from main import ContentFormatter
        cf = ContentFormatter()
        # ETF 금융 테마: 녹색 테이블 + 다채로운 색상 + 넓은 패딩
        cf.H2_STYLE = (
            'style="font-size:22px;font-weight:800;color:#0f172a;'
            'margin:44px 0 18px;padding:14px 0 12px;'
            'border-bottom:3px solid #059669"'
        )
        cf.H3_STYLE = (
            'style="font-size:17px;font-weight:700;color:#1e293b;'
            'margin:24px 0 10px;padding-left:14px;'
            'border-left:4px solid #059669"'
        )
        # 테이블: 녹색 헤더 + 넓은 패딩
        cf.THEAD_STYLE = 'style="background:linear-gradient(135deg,#065f46,#059669)"'
        cf._table_accent = '#059669'
        cf.TABLE_STYLE = (
            'style="width:100%;border-collapse:separate;border-spacing:0;'
            'border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);'
            'margin:28px 0;font-size:15px"'
        )
        cf.TH_STYLE = (
            'style="padding:16px 20px;color:#fff !important;font-weight:700;'
            'text-align:left;font-size:14px;background:none"'
        )
        cf.TD_STYLE = 'style="padding:14px 20px;border-bottom:1px solid #e2e8f0;color:#374151"'
        cf.TD_ALT_STYLE = 'style="padding:14px 20px;border-bottom:1px solid #e2e8f0;color:#374151;background:#f0fdf4"'

        # 투자팁: 깔끔한 골드 박스
        cf.TIP_BOX_STYLE = (
            'style="background:linear-gradient(135deg,#fffbeb,#fef3c7);'
            'border:1px solid #f59e0b;border-radius:14px;padding:22px 28px;margin:28px 0"'
        )
        cf.TIP_BOX_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
            '<span style="font-size:20px">\U0001f4b0</span>'
            '<span style="font-weight:800;color:#92400e;font-size:15px;letter-spacing:0.3px">'
            '\ud22c\uc790 \ud301</span></div>'
        )
        # 핵심 포인트: 밝은 회색 + 그린 보더
        cf.KEY_POINT_STYLE = (
            'style="background:#f8fafb;border-left:5px solid #059669;'
            'border-radius:0 14px 14px 0;padding:20px 28px;margin:28px 0"'
        )
        cf.KEY_POINT_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">'
            '<span style="font-size:18px">\U0001f3af</span>'
            '<span style="font-weight:800;color:#065f46;font-size:15px;letter-spacing:0.3px">'
            '\ud575\uc2ec \ud3ec\uc778\ud2b8</span></div>'
        )
        # 리스크 경고: 빨간 테마
        cf.BLOCKQUOTE_STYLE = (
            'style="background:linear-gradient(135deg,#fff1f2,#ffe4e6);'
            'border-left:5px solid #e11d48;border-radius:0 14px 14px 0;'
            'padding:22px 28px;margin:28px 0;font-style:normal;color:#881337"'
        )
        cf.BLOCKQUOTE_LABEL = (
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:12px">'
            '<span style="font-size:18px">\u26a0\ufe0f</span>'
            '<span style="font-weight:800;color:#be123c;font-size:15px;letter-spacing:0.3px">'
            '\ub9ac\uc2a4\ud06c \uacbd\uace0</span></div>'
        )
        cf.CTA_BOX = ''
        # strong 태그: 붉은색+진한핑크 키워드 하이라이트
        cf._strong_bg = '#fce7f3'

        content = cf.format(content, keyword="ETF 시장분석", category="finance-invest")

        # 후처리 1: 테이블 헤더 색상 강제 → 녹색 (ContentFormatter가 덮어씌울 수 있으므로)
        content = _re.sub(
            r'<thead[^>]*style="background:[^"]*"[^>]*>',
            '<thead style="background:linear-gradient(135deg,#065f46,#059669)">',
            content, flags=_re.IGNORECASE
        )
        # th 흰색 텍스트 + 넉넉한 패딩
        content = _re.sub(
            r'<th(?!ead)[^>]*style="[^"]*"[^>]*>',
            '<th style="padding:14px 20px;color:#ffffff;font-weight:700;text-align:left;font-size:14px;white-space:nowrap">',
            content, flags=_re.IGNORECASE
        )
        # td 넉넉한 패딩 + 첫번째 td는 nowrap
        content = _re.sub(
            r'<td(?!body)[^>]*style="[^"]*"[^>]*>',
            '<td style="padding:13px 20px;border-bottom:1px solid #e2e8f0;color:#1e293b;vertical-align:top">',
            content, flags=_re.IGNORECASE
        )

        # 후처리 2: strong 태그에 붉은/핑크 색상 적용
        content = _re.sub(
            r'<strong style="[^"]*">',
            '<strong style="color:#be123c;background:#fce7f3;padding:1px 4px;border-radius:3px">',
            content
        )
        content = _re.sub(
            r'<strong>(?!<)',
            '<strong style="color:#be123c">',
            content
        )

        log.info("프리미엄 스타일링 적용 완료 (녹색+핑크 테마)")
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

    leading_sectors = daily_data.get("leading_sectors", [])
    payload = _extract_payload(report)
    result = publish_to_wordpress(
        title, content,
        leading_sectors=leading_sectors,
        target_stock=payload.get("target_stock", "")
    )

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
