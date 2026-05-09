"""Render a profile dashboard SVG.

Layout (680 × 900):
    header                y=0   .. 100  big handle, bio subtitle, REV/SHEET
    FIG. 01 cum. stars    y=120 .. 320  full-width line chart
    FIG. 02 top-5 repos   y=340 .. 540  left half, horizontal bars
    FIG. 03 profile radar y=340 .. 540  right half
    FIG. 04 heatmap       y=560 .. 700  53-week contribution grid
    FIG. 05 indicators    y=720 .. 780  4 metric cards in a row
    NOTES                 y=800 .. 850  bottom-left text
    cartouche             y=818 .. 870  bottom-right title block

All strings flow from the `lang` dict — see `cartouche.lang` for the schema.
"""

from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from typing import TypedDict

from .. import lang as _lang_module
from ..lang import format_date_long, month_short, t, tmpl
from . import primitives as P

CANVAS_W = 680
CANVAS_H = 900


class StarPoint(TypedDict):
    date: str
    count: int


class ProfileData(TypedDict, total=False):
    handle: str
    name: str
    bio: str
    joined: str
    followers: int
    following: int
    public_repos: int
    total_stars: int
    total_forks: int
    total_commits_year: int
    languages: list[tuple[str, float]]
    star_history: list[StarPoint]
    top_repos: list[dict]
    contribution_heatmap: list[list[int]]
    radar: dict[str, float]
    notes: list[str]
    rev: str
    date: str


# ──────────────────────────────────────────────────────────────────────────
#  Top-level entry point
# ──────────────────────────────────────────────────────────────────────────

def render(data: ProfileData, theme: dict, lang: dict | None = None) -> str:
    if lang is None:
        lang = _lang_module.load("en")

    parts: list[str] = []

    parts.append(P.svg_open(
        CANVAS_W, CANVAS_H,
        title=f"{data['handle']} — Cartouche profile dashboard",
        desc=(f"Profile telemetry for @{data['handle']}: cumulative star history, "
              f"top repos, contribution heatmap, profile radar."),
    ))
    parts.append(P.defs(theme))
    parts.append(P.background(CANVAS_W, CANVAS_H, theme))
    parts.append(P.watermark(CANVAS_W, CANVAS_H, theme))
    parts.append(P.frame(CANVAS_W, CANVAS_H, theme))

    parts.append(P.header(
        title=f"@{data['handle'].upper()}",
        subtitle=data.get("bio", t(lang, "subtitle_profile")).upper(),
        rev=f"{t(lang, 'rev_prefix')} {data['rev']}",
        sheet=t(lang, "sheet_label"),
        theme=theme,
        width=CANVAS_W,
    ))

    # FIG. 01 — Cumulative star history
    parts.append(_fig_cum_stars(data, theme, lang))

    # FIG. 02 — Top 5 repos (left)
    parts.append(_fig_top_repos(data, theme, lang))

    # FIG. 03 — Profile radar (right)
    parts.append(P.section_label(t(lang, "fig_radar_profile"), 380, 340, theme))
    parts.append('<g transform="translate(520 440)">')
    radar_keys = ["reach", "activity", "breadth", "depth", "polyglot", "engage"]
    radar_axes = [t(lang, f"radar_axis_{k}") for k in radar_keys]
    # Note: data dict uses "engagement" but the axis key is "engage" for brevity.
    radar_data_keys = ["reach", "activity", "breadth", "depth", "polyglot", "engagement"]
    radar_values = [data["radar"].get(k, 0.0) for k in radar_data_keys]
    parts.append(P.radar(0, 0, 80, radar_axes, radar_values, theme))
    parts.append("</g>")

    # FIG. 04 — Contribution heatmap
    parts.append(_fig_heatmap(data, theme, lang))

    # FIG. 05 — Indicators
    parts.append(_fig_indicators(data, theme, lang))

    # Notes + cartouche
    parts.append(P.divider(40, 800, CANVAS_W - 40, theme))
    parts.append(P.notes_block(data.get("notes", []), 40, 824, theme, lang))
    parts.append(P.cartouche(
        handle=data["handle"],
        date=data["date"],
        rev=data["rev"],
        label=tmpl(lang, "label_profile_full",
                   handle=data["handle"].upper(),
                   label=t(lang, "label_profile_telemetry")),
        theme=theme,
        lang=lang,
        x=420, y=818,
    ))

    parts.append(P.credit_line(data["handle"], theme, lang, CANVAS_W, CANVAS_H))
    parts.append(P.svg_close())
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 01 — Cumulative star history
# ──────────────────────────────────────────────────────────────────────────

def _fig_cum_stars(data: ProfileData, theme: dict, lang: dict) -> str:
    history = data["star_history"]
    if not history:
        return P.section_label(
            tmpl(lang, "fig_cum_stars", start="—", end="—"), 40, 124, theme,
        )

    parsed = [(datetime.strptime(p["date"], "%Y-%m-%d").date(), p["count"])
              for p in history]
    start, end = parsed[0][0], parsed[-1][0]
    span_days = max((end - start).days, 1)
    max_stars = max(c for _, c in parsed)
    y_max = _nice_ceil(max_stars)

    points = [((d - start).days, c) for d, c in parsed]
    y_ticks = [(int(y_max * i / 4), str(int(y_max * i / 4))) for i in range(5)]
    x_ticks = _quarter_ticks(start, end, lang)

    parts = [P.section_label(
        tmpl(lang, "fig_cum_stars",
             start=format_date_long(lang, start),
             end=format_date_long(lang, end)),
        40, 124, theme,
    )]
    chart_svg, project = P.line_chart(
        points=points,
        x0=60, y0=160, x1=640, y1=300,
        x_max=span_days, y_max=y_max,
        x_ticks=x_ticks, y_ticks=y_ticks,
        theme=theme,
    )
    parts.append(chart_svg)

    last_x, last_y = project(points[-1][0], points[-1][1])
    parts.append(P.endpoint_marker(last_x, last_y, str(parsed[-1][1]), theme))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 02 — Top 5 repos as horizontal bars
# ──────────────────────────────────────────────────────────────────────────

def _fig_top_repos(data: ProfileData, theme: dict, lang: dict) -> str:
    repos = data.get("top_repos", [])[:5]
    if not repos:
        return P.section_label(t(lang, "fig_top_repos"), 40, 340, theme)

    parts = [P.section_label(t(lang, "fig_top_repos"), 40, 340, theme)]

    row_h = 32
    y0 = 360
    bar_x = 130
    bar_max_w = 180         # 10% shorter than the original 200 to give names more visual breathing room
    name_max_chars = 14     # body role @ size 10 monospace: ~6px/char; 14 chars ≈ 84px, fits in the 90px gap before bar_x
    max_stars = max(r["stars"] for r in repos)

    for i, r in enumerate(repos):
        ry = y0 + i * row_h
        # Truncate names that would touch the bar. The full name is preserved
        # in the underlying data — only the rendered glyph is shortened.
        name = r["name"]
        if len(name) > name_max_chars:
            name = name[:name_max_chars - 1] + "…"
        parts.append(P.text(name, 40, ry + 14, theme, role="body"))
        bar_w = bar_max_w * (r["stars"] / max_stars)
        parts.append(
            f'<rect x="{bar_x}" y="{ry + 4}" width="{bar_max_w}" height="14" '
            f'fill="none" stroke="{theme["frame_inner"]}" stroke-width="0.5"/>'
        )
        parts.append(
            f'<rect x="{bar_x}" y="{ry + 4}" width="{bar_w:.2f}" height="14" '
            f'fill="{theme["data_primary"]}"/>'
        )
        parts.append(P.text(
            tmpl(lang, "top_repo_stars", n=r["stars"]),
            bar_x + bar_max_w + 8, ry + 14, theme, role="dim",
        ))
        parts.append(P.text(
            tmpl(lang, "top_repo_sub",
                 language=r["language"], commits=r["commits_30d"]),
            40, ry + 28, theme, role="dim",
        ))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 04 — 53-week contribution heatmap
# ──────────────────────────────────────────────────────────────────────────

def _fig_heatmap(data: ProfileData, theme: dict, lang: dict) -> str:
    grid = data.get("contribution_heatmap", [])
    if not grid:
        return P.section_label(t(lang, "fig_heatmap"), 40, 560, theme)

    parts = [P.section_label(t(lang, "fig_heatmap"), 40, 560, theme)]

    cell, gap = 10, 1
    cols = len(grid)
    grid_w = cols * (cell + gap) - gap
    grid_x = 58
    grid_y = 580

    def intensity_fill(level: int) -> tuple[str, float]:
        if level == 0:
            return (theme["frame_inner"], 0.15)
        return (theme["data_primary"], 0.25 + 0.25 * level)

    for col_i, week in enumerate(grid):
        for row_i, level in enumerate(week):
            cx = grid_x + col_i * (cell + gap)
            cy = grid_y + row_i * (cell + gap)
            fill, alpha = intensity_fill(level)
            parts.append(
                f'<rect x="{cx}" y="{cy}" width="{cell}" height="{cell}" '
                f'fill="{fill}" fill-opacity="{min(alpha, 1.0):.2f}" rx="1"/>'
            )

    label_x = grid_x - 6
    for row_i, key in [(1, "day_mon"), (3, "day_wed"), (5, "day_fri")]:
        ly = grid_y + row_i * (cell + gap) + cell - 2
        parts.append(P.text(t(lang, key), label_x, ly, theme,
                            role="dim", anchor="end"))

    grid_h = 7 * (cell + gap) - gap
    for col_i in range(0, cols, 4):
        cx = grid_x + col_i * (cell + gap) + cell // 2
        parts.append(
            f'<line x1="{cx}" y1="{grid_y - 4}" x2="{cx}" y2="{grid_y - 1}" '
            f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
        )

    # Legend on the bottom-left of the heatmap, contributions counter on the
    # bottom-right. Splitting them avoids the overlap that occurred when the
    # legend was packed near the right edge alongside the counter text.
    legend_y = grid_y + grid_h + 12
    legend_left_x = grid_x                    # "LESS"/"MOINS" anchored here
    legend_cells_x = legend_left_x + 40       # 40px reserves room for ≤7-char labels
    legend_cells_end = legend_cells_x + 5 * (cell + gap) - gap

    parts.append(P.text(t(lang, "less"), legend_left_x, legend_y + 8, theme,
                        role="dim", anchor="start"))
    for level in range(5):
        fill, alpha = intensity_fill(level)
        lx = legend_cells_x + level * (cell + gap)
        parts.append(
            f'<rect x="{lx}" y="{legend_y}" width="{cell}" height="{cell}" '
            f'fill="{fill}" fill-opacity="{min(alpha, 1.0):.2f}" rx="1"/>'
        )
    parts.append(P.text(t(lang, "more"), legend_cells_end + 6, legend_y + 8,
                        theme, role="dim", anchor="start"))

    total = sum(sum(week) for week in grid)
    parts.append(P.text(
        tmpl(lang, "contribs_total", n=total),
        grid_x + grid_w, legend_y + 8, theme, role="dim", anchor="end",
    ))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 05 — Indicator row
# ──────────────────────────────────────────────────────────────────────────

def _fig_indicators(data: ProfileData, theme: dict, lang: dict) -> str:
    parts = [P.section_label(t(lang, "fig_indicators_profile"), 40, 720, theme)]

    card_w, gap = 140, 10
    cards_x_start = 40
    y = 736

    cards = [
        (t(lang, "card_total_stars"),
         str(data.get("total_stars", 0)),
         tmpl(lang, "n_repos", n=data.get("public_repos", 0))),
        (t(lang, "card_total_forks"),
         str(data.get("total_forks", 0)),
         tmpl(lang, "n_followers", n=data.get("followers", 0))),
        (t(lang, "card_commits_year"),
         str(data.get("total_commits_year", 0)),
         tmpl(lang, "n_following", n=data.get("following", 0))),
        (t(lang, "card_since"),
         data.get("joined", "?")[:7],
         tmpl(lang, "n_years", n=_age_years(data.get("joined", "2024-01-01")))),
    ]

    for i, (label, val, sub) in enumerate(cards):
        x = cards_x_start + i * (card_w + gap)
        parts.append(P.metric_card(x, y, card_w, 50, label, val, sub, theme))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────────

def _nice_ceil(n: int) -> int:
    if n <= 0:
        return 1
    nice_steps = [1, 2, 5, 10, 20, 25, 50, 100]
    magnitude = 1
    while True:
        for step in nice_steps:
            candidate = step * magnitude
            if candidate >= n:
                return candidate
        magnitude *= 10


def _quarter_ticks(start: _date, end: _date, lang: dict) -> list[tuple[int, str]]:
    """For a multi-year span, label one tick per quarter (Q1..Q4) of each year,
    formatted as 'YY/Qn'. For shorter spans, fall back to monthly ticks."""
    if (end - start).days > 365:
        ticks: list[tuple[int, str]] = []
        y = start.year
        while True:
            for q, mm in enumerate([1, 4, 7, 10], start=1):
                boundary = _date(y, mm, 1)
                if boundary < start:
                    continue
                if boundary > end:
                    return ticks
                days = (boundary - start).days
                ticks.append((days, f"{str(y)[-2:]}/Q{q}"))
            y += 1
    # Short span: monthly
    ticks = []
    y, m = start.year, start.month
    while True:
        m += 1
        if m > 12:
            m = 1
            y += 1
        boundary = _date(y, m, 1)
        if boundary > end:
            break
        ticks.append(((boundary - start).days, month_short(lang, m)))
    return ticks


def _age_years(joined_iso: str) -> int:
    joined = datetime.strptime(joined_iso, "%Y-%m-%d").date()
    today = _date.today()
    return max(0, (today - joined).days // 365)
