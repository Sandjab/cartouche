"""Render a repository dashboard SVG.

Layout (680 × 760, viewBox-relative):
    header strip       y=0  .. 100
    FIG. 01 stars      y=120 .. 340  (full width line chart)
    FIG. 02 radar      y=370 .. 580  (left, radar)
    FIG. 03 metrics    y=370 .. 580  (right, 4 cards + language bar)
    NOTES              y=600 .. 680  (bottom-left text)
    cartouche          y=678 .. 730  (bottom-right title block)

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
CANVAS_H = 760


class StarPoint(TypedDict):
    date: str  # YYYY-MM-DD
    count: int  # cumulative stargazers


class Annotation(TypedDict):
    date: str
    count: int
    label_top: str
    label_bottom: str


class RepoData(TypedDict, total=False):
    owner: str
    name: str
    stars: int
    forks: int
    open_issues: int
    closed_issues: int
    commits_30d: int
    commits_total: int
    languages: list[tuple[str, float]]
    stars_30d_delta: int
    forks_30d_delta: int
    star_history: list[StarPoint]
    annotations: list[Annotation]
    radar: dict[str, float]
    notes: list[str]
    rev: str
    date: str
    drawn_by: str


# ──────────────────────────────────────────────────────────────────────────
#  Top-level entry point
# ──────────────────────────────────────────────────────────────────────────


def render(data: RepoData, theme: dict, lang: dict | None = None) -> str:
    """Return a complete SVG document for a single repo dashboard.

    `lang` may be omitted (defaults to English) or loaded via
    `cartouche.lang.load("fr")` etc.
    """
    if lang is None:
        lang = _lang_module.load("en")

    parts: list[str] = []

    parts.append(
        P.svg_open(
            CANVAS_W,
            CANVAS_H,
            title=f"{data['owner']}/{data['name']} — Cartouche dashboard",
            desc=(
                f"Repository telemetry for {data['owner']}/{data['name']}: "
                f"star history, health radar, key metrics."
            ),
        )
    )
    parts.append(P.defs(theme))
    parts.append(P.background(CANVAS_W, CANVAS_H, theme))
    parts.append(P.watermark(CANVAS_W, CANVAS_H, theme))
    parts.append(P.frame(CANVAS_W, CANVAS_H, theme))

    # Header
    parts.append(
        P.header(
            title=data["name"].upper(),
            subtitle=f"{data['owner'].upper()} · {t(lang, 'subtitle_repo')}",
            rev=f"{t(lang, 'rev_prefix')} {data['rev']}",
            sheet=t(lang, "sheet_label"),
            theme=theme,
            width=CANVAS_W,
        )
    )

    # FIG. 01 — Star history
    parts.append(_fig_star_history(data, theme, lang))

    # FIG. 02 — Radar
    parts.append(P.section_label(t(lang, "fig_radar_health"), 40, 370, theme))
    parts.append('<g transform="translate(190 480)">')
    radar_keys = ["stars", "forks", "commits", "code", "tests", "docs"]
    radar_axes = [t(lang, f"radar_axis_{k}") for k in radar_keys]
    radar_values = [data["radar"].get(k, 0.0) for k in radar_keys]
    parts.append(P.radar(0, 0, 90, radar_axes, radar_values, theme))
    parts.append("</g>")

    # FIG. 03 — Metrics
    parts.append(_fig_metrics(data, theme, lang))

    # Notes + cartouche bottom strip
    parts.append(P.divider(40, 600, CANVAS_W - 40, theme))
    parts.append(P.notes_block(data.get("notes", []), 40, 624, theme, lang))
    parts.append(
        P.cartouche(
            handle=data["drawn_by"],
            date=data["date"],
            rev=data["rev"],
            label=tmpl(
                lang,
                "label_repo_full",
                name=data["name"].upper(),
                label=t(lang, "label_repo_telemetry"),
            ),
            theme=theme,
            lang=lang,
        )
    )

    parts.append(P.credit_line(data["drawn_by"], theme, lang, CANVAS_W, CANVAS_H))
    parts.append(P.svg_close())
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 01 — Star history line chart with annotations
# ──────────────────────────────────────────────────────────────────────────


def _fig_star_history(data: RepoData, theme: dict, lang: dict) -> str:
    history = data["star_history"]
    if not history:
        return P.section_label(
            tmpl(lang, "fig_star_history", start="—", end="—"),
            40,
            124,
            theme,
        )

    parsed = [(datetime.strptime(p["date"], "%Y-%m-%d").date(), p["count"]) for p in history]
    start = parsed[0][0]
    end = parsed[-1][0]
    span_days = max((end - start).days, 1)
    max_stars = max(1, max(c for _, c in parsed))
    y_max = _nice_ceil(max_stars)

    points = [((d - start).days, c) for d, c in parsed]
    y_ticks = [(int(y_max * i / 4), str(int(y_max * i / 4))) for i in range(5)]
    x_ticks = _month_ticks(start, end, lang)

    parts = [
        P.section_label(
            tmpl(
                lang,
                "fig_star_history",
                start=format_date_long(lang, start),
                end=format_date_long(lang, end),
            ),
            40,
            124,
            theme,
        )
    ]
    chart_svg, project = P.line_chart(
        points=points,
        x0=60,
        y0=160,
        x1=640,
        y1=320,
        x_max=span_days,
        y_max=y_max,
        x_ticks=x_ticks,
        y_ticks=y_ticks,
        theme=theme,
    )
    parts.append(chart_svg)

    for placed in _layout_annotations(data.get("annotations", []), project, start):
        parts.append(
            P.annotation(
                placed["sx"],
                placed["sy"],
                placed["leader_x"],
                placed["leader_y"],
                primary=placed["label_top"],
                secondary=placed["label_bottom"],
                theme=theme,
                label_anchor=placed["anchor"],
            )
        )

    last_x, last_y = project(points[-1][0], points[-1][1])
    parts.append(P.endpoint_marker(last_x, last_y, str(parsed[-1][1]), theme))

    return "".join(parts)


def _layout_annotations(annotations: list[dict], project, start_date) -> list[dict]:
    """Place each annotation's leader and label using a monotone-staircase
    layout.

    All callouts live in the band between the FIG. 01 title (top, y≈124)
    and the x-axis (bottom, y=320). The band is sliced into horizontal
    tracks 22 pixels apart (`base_track=146`, then `+22` per step).

    Annotations are processed in date order (left → right). For each:
        - Start at `current_floor`, the lowest track used so far
          (initially `base_track`).
        - On the current track, try the preferred anchor, then the
          opposite anchor.
        - If both collide with a previously-placed label box, descend
          one track and try again.
        - Once placed, raise `current_floor` so later annotations never
          go higher than this one.

    This guarantees:
        - Callouts stay between FIG. 01 and the x-axis.
        - The leftmost (earliest) annotation is always at the highest
          track; subsequent annotations are at the same track (no
          collision) or strictly lower (collision).
        - Label boxes never overlap, except in pathological cases where
          the staircase reaches `max_track` — then the last placement
          falls back to the default and accepts the overlap rather than
          dropping the annotation.

    Returns a list parallel to `annotations` (sorted by date), each entry
    augmented with `sx`, `sy`, `leader_x`, `leader_y`, `anchor`.
    """
    if not annotations:
        return []

    # Geometry constants matching the chart layout in _fig_star_history
    # and the annotation primitive (size=7).
    char_w = 4.2  # monospace advance at font-size 7
    chart_x_min = 60
    chart_x_max = 640
    text_pad = 2  # gap between leader_x and the text glyphs
    leader_offset = 50  # horizontal length of the L-shaped leader
    base_track = 146  # highest track, just under the FIG. 01 title
    track_step = 20  # vertical spacing between successive tracks
    max_track = 290  # lowest track, ~30px above the x-axis (y=320)

    sorted_ann = sorted(annotations, key=lambda a: a["date"])
    placed_boxes: list[tuple[float, float, float, float]] = []
    result: list[dict] = []
    current_floor = base_track  # track Y monotonically — never goes back up

    for ann in sorted_ann:
        ann_date = datetime.strptime(ann["date"], "%Y-%m-%d").date()
        sx, sy = project((ann_date - start_date).days, ann["count"])
        label_w = max(len(ann["label_top"]), len(ann["label_bottom"])) * char_w

        primary = "start" if sx <= 480 else "end"
        opposite = "end" if primary == "start" else "start"

        # `sx` and `label_w` are bound as default arguments so this nested
        # function captures the current iteration's values rather than
        # closing over the loop variables (B023).
        def box(anchor: str, leader_y: float, sx: float = sx, label_w: float = label_w):
            lx = sx + leader_offset if anchor == "start" else sx - leader_offset
            if anchor == "start":
                x_l, x_r = lx + text_pad, lx + text_pad + label_w
            else:
                x_l, x_r = lx - text_pad - label_w, lx - text_pad
            return x_l, x_r, leader_y - 8, leader_y + 12, lx

        chosen = None
        ly = current_floor
        while ly <= max_track and chosen is None:
            for anchor in (primary, opposite):
                x_l, x_r, y_t, y_b, lx = box(anchor, ly)
                if x_l < chart_x_min - 24 or x_r > chart_x_max + 24:
                    continue
                if any(
                    x_l < pr and pl < x_r and y_t < pb and pt < y_b
                    for pl, pr, pt, pb in placed_boxes
                ):
                    continue
                chosen = (anchor, ly, lx, x_l, x_r, y_t, y_b)
                break
            if chosen is None:
                ly += track_step

        if chosen is None:
            x_l, x_r, y_t, y_b, lx = box(primary, current_floor)
            chosen = (primary, current_floor, lx, x_l, x_r, y_t, y_b)

        anchor, ly, lx, x_l, x_r, y_t, y_b = chosen
        placed_boxes.append((x_l, x_r, y_t, y_b))
        current_floor = ly  # later annotations may not rise above this track
        result.append(
            {
                **ann,
                "sx": sx,
                "sy": sy,
                "leader_x": lx,
                "leader_y": ly,
                "anchor": anchor,
            }
        )

    return result


# ──────────────────────────────────────────────────────────────────────────
#  FIG. 03 — Metric cards + language bar
# ──────────────────────────────────────────────────────────────────────────


def _fig_metrics(data: RepoData, theme: dict, lang: dict) -> str:
    parts = [P.section_label(t(lang, "fig_indicators_repo"), 350, 370, theme)]

    parts.append(
        P.metric_card(
            350,
            384,
            135,
            58,
            t(lang, "card_stargazers"),
            str(data["stars"]),
            tmpl(lang, "delta_30d", n=data["stars_30d_delta"]),
            theme,
        )
    )
    parts.append(
        P.metric_card(
            495,
            384,
            135,
            58,
            t(lang, "card_forks"),
            str(data["forks"]),
            tmpl(lang, "delta_30d", n=data["forks_30d_delta"]),
            theme,
        )
    )
    parts.append(
        P.metric_card(
            350,
            450,
            135,
            58,
            t(lang, "card_issues_open"),
            str(data["open_issues"]),
            tmpl(lang, "issues_closed", n=data["closed_issues"]),
            theme,
        )
    )
    parts.append(
        P.metric_card(
            495,
            450,
            135,
            58,
            t(lang, "card_commits_30d"),
            str(data["commits_30d"]),
            tmpl(lang, "commits_total", n=data["commits_total"]),
            theme,
        )
    )

    parts.append(_language_bar(data["languages"], 350, 516, 280, 58, theme, lang))
    return "".join(parts)


def _language_bar(
    langs: list[tuple[str, float]], x: int, y: int, w: int, h: int, theme: dict, lang: dict
) -> str:
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="none" stroke="{theme["frame_inner"]}" stroke-width="0.5"/>',
        P.text(t(lang, "languages_breakdown"), x + 8, y + 18, theme, role="dim"),
    ]
    bar_x, bar_y, bar_w, bar_h = x + 8, y + 28, w - 16, 6
    langs_sorted = sorted(langs, key=lambda lg: lg[1], reverse=True)
    top = langs_sorted[:2]
    rest_pct = sum(p for _, p in langs_sorted[2:])
    segments = []
    if len(top) >= 1:
        segments.append((top[0][1] / 100.0, "data_primary"))
    if len(top) >= 2:
        segments.append((top[1][1] / 100.0, "accent"))
    if rest_pct > 0:
        segments.append((rest_pct / 100.0, "frame_inner"))
    parts.append(P.stacked_bar(bar_x, bar_y, bar_w, bar_h, segments, theme))

    legend = " · ".join(f"{name.upper()} {pct:.0f}%" for name, pct in langs_sorted[:3])
    parts.append(P.text(legend, x + 8, y + 52, theme, role="dim"))
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


def _month_ticks(start: _date, end: _date, lang: dict) -> list[tuple[int, str]]:
    """Generate (days_since_start, MONTH_LABEL) tuples for each month boundary
    in [start, end], localized via the lang pack."""
    ticks: list[tuple[int, str]] = []
    y, m = start.year, start.month
    while True:
        m += 1
        if m > 12:
            m = 1
            y += 1
        boundary = _date(y, m, 1)
        if boundary > end:
            break
        days = (boundary - start).days
        ticks.append((days, month_short(lang, m)))
    return ticks
