"""가격 차트 SVG — 의존성 0. 웜톤(밝은 배경·골드 강조), 텍스트는 Pretendard 폴백."""
from __future__ import annotations

from datetime import datetime


def price_chart_svg(points: list[tuple[str, int]], width: int = 640, height: int = 240,
                    title: str = "", note: str = "") -> str:
    """points: [(ts_iso, price)] 시간순. 마지막 점을 강조한다."""
    if not points:
        return ""
    pad_l, pad_r, pad_t, pad_b = 64, 20, 36, 34
    xs = list(range(len(points)))
    ys = [p for _, p in points]
    lo, hi = min(ys), max(ys)
    span = (hi - lo) or max(1, int(hi * 0.05))
    lo_axis, hi_axis = lo - span * 0.15, hi + span * 0.15

    def X(i):
        return pad_l + (width - pad_l - pad_r) * (i / max(1, len(xs) - 1))

    def Y(v):
        return pad_t + (height - pad_t - pad_b) * (1 - (v - lo_axis) / (hi_axis - lo_axis))

    path = " ".join(f"{'M' if i == 0 else 'L'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
    last_x, last_y = X(len(ys) - 1), Y(ys[-1])
    first_d, last_d = points[0][0][:10], points[-1][0][:10]
    grid = "".join(
        f'<line x1="{pad_l}" y1="{Y(v):.1f}" x2="{width-pad_r}" y2="{Y(v):.1f}" stroke="#EDE6D8" stroke-width="1"/>'
        f'<text x="{pad_l-6}" y="{Y(v)+4:.1f}" font-size="11" text-anchor="end" fill="#8A7E6B">{v:,}</text>'
        for v in (lo, hi)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" '
        f'style="max-width:{width}px;font-family:Pretendard,-apple-system,sans-serif;background:#FFFDF8;border-radius:12px">'
        f'<text x="{pad_l}" y="22" font-size="14" font-weight="700" fill="#2B2418">{_esc(title)}</text>'
        f"{grid}"
        f'<path d="{path}" fill="none" stroke="#B8902E" stroke-width="2.5" stroke-linejoin="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="#B8902E" stroke="#FFFDF8" stroke-width="2"/>'
        f'<text x="{min(last_x, width-pad_r-60):.1f}" y="{max(pad_t+12, last_y-10):.1f}" font-size="12" font-weight="700" fill="#2B2418">{ys[-1]:,}원</text>'
        f'<text x="{pad_l}" y="{height-12}" font-size="11" fill="#8A7E6B">{first_d}</text>'
        f'<text x="{width-pad_r}" y="{height-12}" font-size="11" text-anchor="end" fill="#8A7E6B">{last_d}</text>'
        f'<text x="{width-pad_r}" y="22" font-size="11" text-anchor="end" fill="#8A7E6B">{_esc(note)}</text>'
        "</svg>"
    )


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
