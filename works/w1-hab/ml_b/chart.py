"""Dependency-free SVG chart: block permutation importance with 95% CI."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

COLORS = {
    "питание": "#2e7d32",
    "сон": "#1565c0",
    "стресс": "#c62828",
    "активность": "#ef6c00",
    "контроль": "#6a1b9a",
}


def _ticks(low: float, high: float, count: int = 5) -> list[float]:
    span = high - low
    if span <= 0:
        return [low]
    step = span / count
    return [low + step * index for index in range(count + 1)]


def write_importance_svg(
    blocks: pd.DataFrame,
    path: Path,
    title: str = "Вклад блоков: Δ ROC AUC на test (95% CI)",
) -> Path:
    """Draw horizontal bars with error bars; return the written path."""
    frame = blocks.copy()
    frame = frame.sort_values("perm_importance", ascending=True).reset_index(drop=True)

    width, height = 940, 90 + 58 * len(frame)
    left, right, top = 190, 790, 58
    plot_width = right - left

    low = min(0.0, float(frame["ci_low"].min()))
    high = max(0.0, float(frame["ci_high"].max()))
    padding = (high - low) * 0.08 or 0.01
    low -= padding
    high += padding

    def x(value: float) -> float:
        return left + (value - low) / (high - low) * plot_width

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">',
        "<style>"
        "text{font-family:'Segoe UI',Arial,sans-serif;fill:#1f2937}"
        ".title{font-size:17px;font-weight:600}"
        ".label{font-size:14px}"
        ".value{font-size:12px;fill:#4b5563}"
        ".axis{stroke:#9ca3af;stroke-width:1}"
        "</style>",
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text class="title" x="{left}" y="30">{title}</text>',
    ]

    for tick in _ticks(low, high):
        xpos = x(tick)
        parts.append(
            f'<line class="axis" x1="{xpos:.1f}" y1="{top - 8}" '
            f'x2="{xpos:.1f}" y2="{height - 34}"/>'
        )
        parts.append(
            f'<text class="value" x="{xpos:.1f}" y="{height - 16}" '
            f'text-anchor="middle">{tick:.3f}</text>'
        )

    zero = x(0.0)
    parts.append(
        f'<line x1="{zero:.1f}" y1="{top - 8}" x2="{zero:.1f}" '
        f'y2="{height - 34}" stroke="#374151" stroke-width="1.5"/>'
    )

    for index, row in frame.iterrows():
        center = top + 29 * index + 20
        bar_top = center - 11
        value = float(row["perm_importance"])
        start, end = sorted((x(0.0), x(value)))
        color = COLORS.get(str(row["block"]), "#455a64")
        parts.append(
            f'<text class="label" x="{left - 16}" y="{center + 5}" '
            f'text-anchor="end">{row["block"]}</text>'
        )
        parts.append(
            f'<rect x="{start:.1f}" y="{bar_top}" width="{max(end - start, 1):.1f}" '
            f'height="22" rx="3" fill="{color}" opacity="0.85"/>'
        )
        ci_low, ci_high = x(float(row["ci_low"])), x(float(row["ci_high"]))
        parts.append(
            f'<line x1="{ci_low:.1f}" y1="{center}" x2="{ci_high:.1f}" '
            f'y2="{center}" stroke="#111827" stroke-width="1.6"/>'
        )
        for edge in (ci_low, ci_high):
            parts.append(
                f'<line x1="{edge:.1f}" y1="{center - 6}" x2="{edge:.1f}" '
                f'y2="{center + 6}" stroke="#111827" stroke-width="1.6"/>'
            )
        parts.append(
            f'<text class="value" x="{right + 14}" y="{center + 4}">'
            f'{value:+.3f} [{float(row["ci_low"]):+.3f}; {float(row["ci_high"]):+.3f}]</text>'
        )

    parts.append(
        f'<text class="value" x="{left}" y="{height - 2}">'
        "Permutation importance на test, 1000 повторов. 0 = блок не улучшает ранжирование."
        "</text>"
    )
    parts.append("</svg>")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path
