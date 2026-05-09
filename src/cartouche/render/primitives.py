"""SVG primitives for Cartouche dashboards.

These functions return SVG fragments as strings. They consume theme tokens
(see themes.py) and never hardcode colors. Composing a dashboard means
calling these in sequence and joining the output.

Coordinate system: viewBox is canvas_w × canvas_h, origin top-left.
By convention, the safe area is x=40..canvas_w-40, y=40..canvas_h-40.

All text is monospace by default — that's the Cartouche identity.
The `MONO_STACK` falls back through SF Mono / JetBrains Mono / Consolas
to whatever the host renders. Web fonts are intentionally not used
because GitHub strips them when rendering README SVGs.
"""

from __future__ import annotations

import math
from typing import Iterable, Sequence

MONO_STACK = "ui-monospace, 'SF Mono', 'JetBrains Mono', 'Cascadia Code', Consolas, monospace"

# ──────────────────────────────────────────────────────────────────────────
#  Document-level
# ──────────────────────────────────────────────────────────────────────────

def svg_open(width: int, height: int, title: str, desc: str) -> str:
    """Opening <svg> tag with title/desc for accessibility."""
    return (
        f'<svg width="100%" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        f'<title>{_esc(title)}</title><desc>{_esc(desc)}</desc>'
    )


def svg_close() -> str:
    return "</svg>"


def defs(theme: dict) -> str:
    """<defs> block with the two grid patterns. Call once per SVG."""
    fine = theme["grid_fine"]
    major = theme["grid_major"]
    return (
        '<defs>'
        f'<pattern id="grid-fine" width="10" height="10" patternUnits="userSpaceOnUse">'
        f'<path d="M10 0H0V10" fill="none" stroke="{fine}" stroke-width="0.4"/></pattern>'
        f'<pattern id="grid-major" width="50" height="50" patternUnits="userSpaceOnUse">'
        f'<path d="M50 0H0V50" fill="none" stroke="{major}" stroke-width="0.5"/></pattern>'
        '</defs>'
    )


def background(width: int, height: int, theme: dict) -> str:
    """Solid background + two grid layers stacked."""
    return (
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="{theme["bg"]}"/>'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#grid-fine)"/>'
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="url(#grid-major)"/>'
    )


def frame(width: int, height: int, theme: dict, margin: int = 20) -> str:
    """Outer + inner double frame. The signature double-line of technical drawing."""
    inset = margin + 4
    return (
        f'<rect x="{margin}" y="{margin}" '
        f'width="{width - 2*margin}" height="{height - 2*margin}" '
        f'fill="none" stroke="{theme["frame"]}" stroke-width="0.7"/>'
        f'<rect x="{inset}" y="{inset}" '
        f'width="{width - 2*inset}" height="{height - 2*inset}" '
        f'fill="none" stroke="{theme["frame_inner"]}" stroke-width="0.4"/>'
    )


# ──────────────────────────────────────────────────────────────────────────
#  Text helpers
# ──────────────────────────────────────────────────────────────────────────

def text(content: str, x: float, y: float, theme: dict, *,
         role: str = "secondary", anchor: str = "start",
         size: int | None = None, weight: int | None = None) -> str:
    """Render a <text> element, themed by role.

    Roles map to (default size, default weight, fill token):
        title     32  700  text_primary
        label     10  400  text_label    (UPPERCASE, tracked, section headers)
        num       22  700  text_primary  (large numerals)
        dim        9  400  text_secondary (tick labels, captions)
        caption  11  400  text_secondary
        body     10  400  text_primary
        accent     9  400  accent         (annotation callouts)

    Override `size` or `weight` to deviate. `anchor` ∈ {start, middle, end}.
    """
    role_defaults = {
        "title":   (32, 700, theme["text_primary"]),
        "label":   (10, 400, theme["text_label"]),
        "num":     (22, 700, theme["text_primary"]),
        "dim":     (9,  400, theme["text_secondary"]),
        "caption": (11, 400, theme["text_secondary"]),
        "body":    (10, 400, theme["text_primary"]),
        "accent":  (9,  400, theme["accent"]),
    }
    default_size, default_weight, fill = role_defaults[role]
    s = size if size is not None else default_size
    w = weight if weight is not None else default_weight
    letter_spacing = "0.18em" if role == "title" else (
        "0.12em" if role == "label" else "0.08em" if role == "dim" else "normal"
    )
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO_STACK}" '
        f'font-size="{s}" font-weight="{w}" fill="{fill}" '
        f'text-anchor="{anchor}" letter-spacing="{letter_spacing}">{_esc(content)}</text>'
    )


# ──────────────────────────────────────────────────────────────────────────
#  Header strip + cartouche
# ──────────────────────────────────────────────────────────────────────────

def header(title: str, subtitle: str, rev: str, sheet: str,
           theme: dict, *, width: int = 680) -> str:
    """Top header strip: big title on the left, REV/SHEET on the right.
    Closes with a horizontal divider.

    `rev` and `sheet` are pre-formatted strings ("REV A.04", "SHEET 01 / 01")
    so that callers can localize them via the lang module before passing in.
    """
    parts = [
        text(title, 40, 68, theme, role="title"),
        text(subtitle, 40, 86, theme, role="dim"),
        text(rev, width - 40, 68, theme, role="label", anchor="end"),
        text(sheet, width - 40, 84, theme, role="dim", anchor="end"),
        f'<line x1="40" y1="98" x2="{width - 40}" y2="98" '
        f'stroke="{theme["frame"]}" stroke-width="0.7"/>',
    ]
    return "".join(parts)


def cartouche(handle: str, date: str, rev: str, label: str,
              theme: dict, lang: dict, *, x: int = 420, y: int = 678,
              w: int = 220, h: int = 52) -> str:
    """The bottom-right title block, in three rows like a real architectural
    drawing title block:

        ┌──────────┬────────────┬──────────┐
        │ DRAWN BY │ DATE       │ REV      │   ← top row: field labels
        ├──────────┼────────────┼──────────┤
        │ HANDLE   │ 2026-05-09 │ A.04     │   ← middle row: values, in 3 cols
        ├──────────┴────────────┴──────────┤   ← horizontal divider closes cols
        │ TITLE OF THE DRAWING             │   ← bottom row: title, full width
        └──────────────────────────────────┘

    Field labels come from `lang` so they translate.
    """
    col1 = x + 90
    col2 = x + 155
    # Three rows separated by two horizontal dividers
    labels_row_bottom = y + 13      # between labels row and values row
    values_row_bottom = y + 38      # between values row and title row
    parts = [
        # Outer frame
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="none" stroke="{theme["frame"]}" stroke-width="0.7"/>',
        # Horizontal dividers
        f'<line x1="{x}" y1="{labels_row_bottom}" x2="{x + w}" y2="{labels_row_bottom}" '
        f'stroke="{theme["frame"]}" stroke-width="0.7"/>',
        f'<line x1="{x}" y1="{values_row_bottom}" x2="{x + w}" y2="{values_row_bottom}" '
        f'stroke="{theme["frame"]}" stroke-width="0.7"/>',
        # Column dividers — only inside the labels + values rows; the title
        # row is a single band (no vertical dividers crossing it).
        f'<line x1="{col1}" y1="{y}" x2="{col1}" y2="{values_row_bottom}" '
        f'stroke="{theme["frame"]}" stroke-width="0.7"/>',
        f'<line x1="{col2}" y1="{y}" x2="{col2}" y2="{values_row_bottom}" '
        f'stroke="{theme["frame"]}" stroke-width="0.7"/>',
        # Field labels (tiny) — pulled from the lang pack
        text(lang["labels"]["drawn_by"], x + 4, y + 10, theme, role="dim", size=7),
        text(lang["labels"]["date_label"], col1 + 4, y + 10, theme, role="dim", size=7),
        text(lang["labels"]["rev_label"], col2 + 4, y + 10, theme, role="dim", size=7),
        # Field values, centered vertically in the values row (y+13..y+38)
        text(handle.upper(), x + 4, y + 30, theme, role="body", size=11, weight=400),
        text(date, col1 + 4, y + 30, theme, role="body", size=10, weight=400),
        text(rev, col2 + 4, y + 30, theme, role="body", size=11, weight=400),
        # Title row — single band, no dividers, baseline centered in y+38..y+52
        text(label, x + 4, y + 49, theme, role="dim"),
    ]
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  Chart axes + curve
# ──────────────────────────────────────────────────────────────────────────

def line_chart(points: Sequence[tuple[float, float]],
               x0: float, y0: float, x1: float, y1: float,
               x_max: float, y_max: float,
               x_ticks: Sequence[tuple[float, str]],
               y_ticks: Sequence[tuple[float, str]],
               theme: dict) -> tuple[str, callable]:
    """Render a line chart in the rect (x0,y0)-(x1,y1) and return:
       - the SVG fragment
       - a `project(data_x, data_y) -> (svg_x, svg_y)` function for callers
         to position annotations on top of the curve.

    `points` are (data_x, data_y) tuples.
    `x_ticks` / `y_ticks` are (data_value, label) pairs.
    """
    def project(dx: float, dy: float) -> tuple[float, float]:
        sx = x0 + (dx / x_max) * (x1 - x0)
        sy = y1 - (dy / y_max) * (y1 - y0)
        return sx, sy

    parts = []
    # Axes
    parts.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" '
        f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
    )
    parts.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" '
        f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
    )
    # Y ticks + labels
    for value, label in y_ticks:
        _, ty = project(0, value)
        parts.append(
            f'<line x1="{x0 - 4}" y1="{ty}" x2="{x0}" y2="{ty}" '
            f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
        )
        parts.append(text(label, x0 - 8, ty + 3, theme, role="dim", anchor="end"))
    # X ticks + labels
    for value, label in x_ticks:
        tx, _ = project(value, 0)
        parts.append(
            f'<line x1="{tx}" y1="{y1}" x2="{tx}" y2="{y1 + 4}" '
            f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
        )
        parts.append(text(label, tx, y1 + 16, theme, role="dim", anchor="middle"))
    # Curve
    if points:
        path_cmds = ["M"]
        for i, (dx, dy) in enumerate(points):
            sx, sy = project(dx, dy)
            path_cmds.append(f"{sx:.2f},{sy:.2f}")
            if i == 0 and len(points) > 1:
                path_cmds.append("L")
        # Drop the trailing 'L' if the loop added it after the last point
        if path_cmds[-1] == "L":
            path_cmds.pop()
        d = " ".join(path_cmds)
        parts.append(
            f'<path d="{d}" fill="none" stroke="{theme["data_primary"]}" '
            f'stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>'
        )

    return "".join(parts), project


def annotation(svg_x: float, svg_y: float,
               leader_to_x: float, leader_to_y: float,
               primary: str, secondary: str,
               theme: dict, *, label_anchor: str = "start") -> str:
    """Drop a circular marker at (svg_x, svg_y), draw an L-shaped dashed leader
    to (leader_to_x, leader_to_y), and place a two-line callout at the leader end.

    `primary` is the accent-colored top line ("// PREMIÈRE ÉTOILE — 2025-10-08").
    `secondary` is the dim continuation line ("push initial · v0.1.0").
    """
    text_x = leader_to_x + 4 if label_anchor == "start" else leader_to_x - 4
    return (
        f'<circle cx="{svg_x}" cy="{svg_y}" r="2.4" fill="{theme["accent"]}"/>'
        f'<line x1="{svg_x}" y1="{svg_y}" x2="{svg_x}" y2="{leader_to_y}" '
        f'stroke="{theme["accent"]}" stroke-width="0.5" '
        f'stroke-dasharray="2,2" fill="none"/>'
        f'<line x1="{svg_x}" y1="{leader_to_y}" x2="{leader_to_x}" y2="{leader_to_y}" '
        f'stroke="{theme["accent"]}" stroke-width="0.5" '
        f'stroke-dasharray="2,2" fill="none"/>'
        + text(primary, text_x, leader_to_y - 4, theme, role="accent", anchor=label_anchor)
        + text(secondary, text_x, leader_to_y + 7, theme, role="dim", anchor=label_anchor)
    )


def endpoint_marker(svg_x: float, svg_y: float, value: str, theme: dict) -> str:
    """Highlight the last point of a curve with a stroked circle + value label."""
    return (
        f'<circle cx="{svg_x}" cy="{svg_y}" r="3" fill="{theme["data_primary"]}" '
        f'stroke="{theme["text_primary"]}" stroke-width="0.8"/>'
        + text(value, svg_x - 6, svg_y - 10, theme, role="num", size=14, anchor="end")
    )


# ──────────────────────────────────────────────────────────────────────────
#  Radar chart
# ──────────────────────────────────────────────────────────────────────────

def radar(cx: float, cy: float, radius: float,
          axis_labels: Sequence[str], values: Sequence[float],
          theme: dict, *, levels: int = 4) -> str:
    """Render a hexagonal radar (or n-gon if len(axis_labels) != 6).

    `values` are normalized 0..1 distances along each axis.
    Axes start at the top (north) and go clockwise.
    """
    n = len(axis_labels)
    if n != len(values):
        raise ValueError("axis_labels and values must have the same length")

    # Compute axis endpoints (normalized to radius=1)
    def axis_point(i: int, scale: float) -> tuple[float, float]:
        # Start at top (-90° in math coords), go clockwise
        angle = -math.pi / 2 + 2 * math.pi * i / n
        return (cx + scale * radius * math.cos(angle),
                cy + scale * radius * math.sin(angle))

    parts = []

    # Concentric polygons (level rings)
    for level in range(levels, 0, -1):
        scale = level / levels
        ring = [axis_point(i, scale) for i in range(n)]
        pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in ring)
        dash = "" if level == levels else 'stroke-dasharray="1,2"'
        parts.append(
            f'<polygon points="{pts}" fill="none" '
            f'stroke="{theme["axis"]}" stroke-width="0.5" {dash}/>'
        )

    # Spokes
    for i in range(n):
        ex, ey = axis_point(i, 1.0)
        parts.append(
            f'<line x1="{cx}" y1="{cy}" x2="{ex:.2f}" y2="{ey:.2f}" '
            f'stroke="{theme["axis"]}" stroke-width="0.5"/>'
        )

    # Data polygon
    data_pts = [axis_point(i, max(0.0, min(1.0, v))) for i, v in enumerate(values)]
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in data_pts)
    parts.append(
        f'<polygon points="{pts}" fill="{theme["data_primary"]}" '
        f'fill-opacity="{theme["data_fill_opacity"]}" '
        f'stroke="{theme["data_primary"]}" stroke-width="1.2"/>'
    )
    for x, y in data_pts:
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.2" '
            f'fill="{theme["data_primary"]}"/>'
        )

    # Axis labels (placed slightly outside the outer ring)
    label_radius = radius + 14
    for i, label in enumerate(axis_labels):
        lx, ly = axis_point(i, label_radius / radius)
        # Pick anchor by horizontal position
        if abs(lx - cx) < 4:
            anchor = "middle"
        elif lx > cx:
            anchor = "start"
        else:
            anchor = "end"
        parts.append(text(label, lx, ly + 3, theme, role="dim", anchor=anchor))

    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────
#  Metric cards & misc
# ──────────────────────────────────────────────────────────────────────────

def metric_card(x: float, y: float, w: float, h: float,
                label: str, value: str, sub: str, theme: dict) -> str:
    """A bordered card with a small label, a big number, and a small sublabel."""
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="none" stroke="{theme["frame_inner"]}" stroke-width="0.5"/>'
        + text(label, x + 8, y + 18, theme, role="dim")
        + text(value, x + 8, y + 46, theme, role="num")
        + text(sub, x + w - 8, y + 46, theme, role="dim", anchor="end")
    )


def stacked_bar(x: float, y: float, w: float, h: float,
                segments: Sequence[tuple[float, str]],
                theme: dict) -> str:
    """Horizontal stacked bar. `segments` are (fraction_0_to_1, color_token_name).

    Color tokens accepted: 'data_primary', 'accent', 'frame_inner'.
    """
    parts = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
        f'fill="none" stroke="{theme["frame_inner"]}" stroke-width="0.5"/>'
    ]
    cursor = x
    for frac, token in segments:
        seg_w = w * frac
        parts.append(
            f'<rect x="{cursor}" y="{y}" width="{seg_w:.2f}" height="{h}" '
            f'fill="{theme[token]}"/>'
        )
        cursor += seg_w
    return "".join(parts)


def section_label(label: str, x: float, y: float, theme: dict, *,
                  width: int = 680) -> str:
    """A FIG. header with a short rule line under it."""
    return text(label, x, y, theme, role="label")


def divider(x1: float, y: float, x2: float, theme: dict) -> str:
    return (f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" '
            f'stroke="{theme["frame"]}" stroke-width="0.7"/>')


def notes_block(notes: Sequence[str], x: float, y_start: float,
                theme: dict, lang: dict, *, line_h: int = 14) -> str:
    """A list of short note lines, one per row, prefixed with ▸.
    Header label comes from the lang pack."""
    parts = [text(lang["labels"]["notes_label"], x, y_start - 6, theme, role="label")]
    for i, note in enumerate(notes):
        parts.append(text(f"▸ {note}", x, y_start + 10 + i * line_h, theme, role="dim"))
    return "".join(parts)


def credit_line(handle: str, theme: dict, lang: dict,
                canvas_w: int, canvas_h: int) -> str:
    """Watermark placed below the outer frame, bottom-right.

    Lives in the 20-pixel band between the outer frame (which ends at
    canvas_h - 20) and the canvas edge. Pulled from the lang pack so the
    string can be customized via overlay, but is identical in EN and FR
    by default (the "Clauded" pun is intentional and intraducible).
    """
    return text(
        lang["templates"]["proudly_clauded"].format(handle=handle),
        canvas_w - 22, canvas_h - 8,
        theme, role="dim", anchor="end", size=8,
    )


# ──────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────────

def _esc(s: str) -> str:
    """Minimal XML escape for text content."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))
