"""Sanity tests for Cartouche.

These don't hit the GitHub API. They use the `mock` module fixtures and
check that:
  - all themes have the required token keys
  - both built-in lang packs have all required keys + months
  - both renderers produce well-formed SVG with strings from the lang pack
  - the lang overlay merge does the right thing
  - the CLI's --mock path works end-to-end with --lang/--lang-file

Run with: PYTHONPATH=src python -m pytest tests/
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET

import pytest

from cartouche import lang as lang_module
from cartouche.mock import mock_profile, mock_repo
from cartouche.render import profile, repo
from cartouche.themes import THEMES, get_theme, list_themes

REQUIRED_THEME_TOKENS = {
    "bg", "grid_fine", "grid_major", "frame", "frame_inner", "axis",
    "text_primary", "text_secondary", "text_label",
    "data_primary", "data_fill_opacity", "accent",
    "watermark", "watermark_opacity",
}

# These tokens are not hex colors and shouldn't be validated as such.
NON_COLOR_TOKENS = {"data_fill_opacity", "watermark", "watermark_opacity"}

REQUIRED_LANG_LABELS = {
    "subtitle_repo", "subtitle_profile", "rev_prefix", "sheet_label",
    "fig_radar_health", "fig_indicators_repo", "fig_top_repos",
    "fig_radar_profile", "fig_heatmap", "fig_indicators_profile",
    "card_stargazers", "card_forks", "card_issues_open", "card_commits_30d",
    "card_total_stars", "card_total_forks", "card_commits_year", "card_since",
    "languages_breakdown", "notes_label", "drawn_by", "date_label", "rev_label",
    "less", "more",
    "radar_axis_stars", "radar_axis_forks", "radar_axis_commits",
    "radar_axis_code", "radar_axis_tests", "radar_axis_docs",
    "radar_axis_reach", "radar_axis_activity", "radar_axis_breadth",
    "radar_axis_depth", "radar_axis_polyglot", "radar_axis_engage",
    "label_repo_telemetry", "label_profile_telemetry",
    "day_mon", "day_wed", "day_fri",
}

REQUIRED_LANG_TEMPLATES = {
    "fig_star_history", "fig_cum_stars",
    "first_star_top", "first_star_bottom",
    "spike_top", "spike_bottom",
    "delta_30d", "issues_closed", "commits_total",
    "n_repos", "n_followers", "n_following", "n_years",
    "contribs_total",
    "top_repo_stars", "top_repo_sub",
    "stack_summary", "license_summary",
    "profile_notes_totals", "profile_notes_stack", "profile_notes_top",
    "label_repo_full", "label_profile_full",
    "proudly_clauded",
}


# ──────────────────────────────────────────────────────────────────────────
#  Theme contract
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name", list_themes())
def test_theme_has_all_tokens(name: str):
    theme = get_theme(name)
    missing = REQUIRED_THEME_TOKENS - set(theme)
    assert not missing, f"Theme {name!r} missing tokens: {missing}"


@pytest.mark.parametrize("name", list_themes())
def test_theme_colors_are_hex(name: str):
    theme = get_theme(name)
    for k in REQUIRED_THEME_TOKENS - NON_COLOR_TOKENS:
        assert re.match(r"^#[0-9a-fA-F]{6}$", theme[k])


def test_themes_count():
    # Smoke test — bumps every time we add or drop a theme. Keeps surprises
    # out of the registry without preventing growth.
    assert len(THEMES) == 16
    families = {name.rsplit("-", 1)[0] for name in THEMES}
    for family in families:
        assert f"{family}-light" in THEMES, f"{family!r} missing light variant"
        assert f"{family}-dark" in THEMES, f"{family!r} missing dark variant"


# ──────────────────────────────────────────────────────────────────────────
#  Lang contract
# ──────────────────────────────────────────────────────────────────────────

def test_two_builtin_langs():
    assert set(lang_module.list_builtin()) == {"en", "fr"}


@pytest.mark.parametrize("code", lang_module.list_builtin())
def test_lang_has_all_required_keys(code: str):
    pack = lang_module.load(code)
    missing_labels = REQUIRED_LANG_LABELS - set(pack["labels"])
    assert not missing_labels, f"Lang {code!r} missing labels: {missing_labels}"
    missing_tmpl = REQUIRED_LANG_TEMPLATES - set(pack["templates"])
    assert not missing_tmpl, f"Lang {code!r} missing templates: {missing_tmpl}"
    assert len(pack["months_short"]) == 12
    assert len(pack["months_long"]) == 12


def test_lang_unknown_code_raises():
    with pytest.raises(KeyError):
        lang_module.load("xx-NOPE")


def test_lang_overlay_merges_deeply(tmp_path):
    overlay = {
        "labels": {"drawn_by": "PAR"},
        "templates": {"n_years": "{n} années"},
    }
    p = tmp_path / "fr-strong.json"
    p.write_text(json.dumps(overlay), encoding="utf-8")
    merged = lang_module.load("fr", overlay_path=str(p))
    assert merged["labels"]["drawn_by"] == "PAR"
    assert merged["templates"]["n_years"] == "{n} années"
    # Untouched key still present
    assert merged["labels"]["less"] == "MOINS"
    # Helpers work
    assert lang_module.t(merged, "drawn_by") == "PAR"
    assert lang_module.tmpl(merged, "n_years", n=3) == "3 années"


def test_lang_helpers():
    en = lang_module.load("en")
    assert lang_module.t(en, "less") == "LESS"
    assert lang_module.tmpl(en, "delta_30d", n=5) == "+5 / 30D"
    assert lang_module.month_short(en, 1) == "JAN"
    assert lang_module.month_long(en, 1) == "Jan"


# ──────────────────────────────────────────────────────────────────────────
#  Renderers — across 16 themes × 2 langs = 32 combinations each
# ──────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("theme_name", list_themes())
@pytest.mark.parametrize("lang_code", lang_module.list_builtin())
def test_repo_render_well_formed(theme_name: str, lang_code: str):
    pack = lang_module.load(lang_code)
    svg = repo.render(mock_repo("Sandjab", "Athanor", lang=pack),
                      get_theme(theme_name), lang=pack)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "ATHANOR" in svg
    assert "SANDJAB" in svg
    # All 3 figs present
    for n in (1, 2, 3):
        assert f"FIG. 0{n}" in svg
    # Lang-specific check: drawn_by label appears
    assert pack["labels"]["drawn_by"] in svg


@pytest.mark.parametrize("theme_name", list_themes())
@pytest.mark.parametrize("lang_code", lang_module.list_builtin())
def test_profile_render_well_formed(theme_name: str, lang_code: str):
    pack = lang_module.load(lang_code)
    svg = profile.render(mock_profile("Sandjab", lang=pack),
                         get_theme(theme_name), lang=pack)
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert "@SANDJAB" in svg
    for n in range(1, 6):
        assert f"FIG. 0{n}" in svg
    rects = svg.count("<rect")
    assert rects >= 371  # 53*7 heatmap cells minimum


def test_render_defaults_to_english():
    """If lang is omitted, EN should be used."""
    svg = repo.render(mock_repo("Sandjab", "Athanor"), get_theme("blueprint-light"))
    # EN-specific strings
    assert "HEALTH RADAR" in svg
    assert "INDICATORS" in svg
    assert "// FIRST STAR" in svg


def test_render_french_uses_french():
    fr = lang_module.load("fr")
    svg = repo.render(mock_repo("Sandjab", "Athanor", lang=fr),
                      get_theme("blueprint-light"), lang=fr)
    assert "RADAR DE SANTÉ" in svg
    assert "INDICATEURS" in svg
    assert "PREMIÈRE ÉTOILE" in svg


def test_profile_truncates_long_repo_names():
    """A repo name longer than 14 chars should be rendered truncated with an
    ellipsis so it never touches the star bar. Mock data ships with
    'apikoltar-corpus' (16 chars) which exercises this path."""
    pack = lang_module.load("en")
    svg = profile.render(mock_profile("Sandjab", lang=pack),
                         get_theme("blueprint-light"), lang=pack)
    # The full name must NOT be present, the truncated version must.
    assert "apikoltar-corpus" not in svg
    assert "apikoltar-cor…" in svg
    # Short names stay intact
    assert "athanor" in svg
    assert "cartouche" in svg


def test_credit_line_present_on_both_dashboards():
    """The 'Proudly Clauded by @<handle>' watermark sits below the frame on
    both repo and profile dashboards. It uses the data's handle / owner so
    different users get their own credit automatically."""
    pack = lang_module.load("en")
    repo_svg = repo.render(mock_repo("Sandjab", "Athanor", lang=pack),
                           get_theme("blueprint-light"), lang=pack)
    prof_svg = profile.render(mock_profile("Sandjab", lang=pack),
                              get_theme("blueprint-light"), lang=pack)
    assert "Proudly Clauded by @Sandjab" in repo_svg
    assert "Proudly Clauded by @Sandjab" in prof_svg

    # Different handle → different credit
    other = repo.render(mock_repo("Octocat", "myrepo", lang=pack),
                        get_theme("blueprint-light"), lang=pack)
    assert "Proudly Clauded by @Octocat" in other
    assert "Proudly Clauded by @Sandjab" not in other


# ──────────────────────────────────────────────────────────────────────────
#  CLI
# ──────────────────────────────────────────────────────────────────────────

def test_cli_themes(capsys):
    from cartouche.cli import main
    rc = main(["themes"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert set(out) == set(list_themes())


def test_cli_langs(capsys):
    from cartouche.cli import main
    rc = main(["langs"])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert set(out) == set(lang_module.list_builtin())


def test_cli_repo_mock_default_lang(tmp_path):
    from cartouche.cli import main
    out_path = tmp_path / "out.svg"
    rc = main(["repo", "Sandjab/Athanor", "--out", str(out_path), "--mock"])
    assert rc == 0
    content = out_path.read_text()
    assert "ATHANOR" in content
    # Default is EN
    assert "HEALTH RADAR" in content


def test_cli_repo_mock_french(tmp_path):
    from cartouche.cli import main
    out_path = tmp_path / "out.svg"
    rc = main([
        "repo", "Sandjab/Athanor",
        "--lang", "fr",
        "--out", str(out_path),
        "--mock",
    ])
    assert rc == 0
    content = out_path.read_text()
    assert "RADAR DE SANTÉ" in content


def test_cli_repo_lang_file(tmp_path):
    from cartouche.cli import main
    overlay_path = tmp_path / "custom.json"
    overlay_path.write_text(json.dumps({
        "labels": {"fig_radar_health": "FIG. 02 — VITAL SIGNS"},
    }))
    out_path = tmp_path / "out.svg"
    rc = main([
        "repo", "Sandjab/Athanor",
        "--lang-file", str(overlay_path),
        "--out", str(out_path),
        "--mock",
    ])
    assert rc == 0
    content = out_path.read_text()
    assert "VITAL SIGNS" in content


def test_cli_profile_mock_french(tmp_path):
    from cartouche.cli import main
    out_path = tmp_path / "out.svg"
    rc = main([
        "profile", "Sandjab",
        "--lang", "fr",
        "--theme", "vellum-light",
        "--out", str(out_path),
        "--mock",
    ])
    assert rc == 0
    content = out_path.read_text()
    assert "@SANDJAB" in content
    assert "RADAR PROFIL" in content


def test_cli_rejects_unknown_lang():
    from cartouche.cli import main
    with pytest.raises(SystemExit) as exc:
        main(["repo", "Sandjab/Athanor", "--lang", "xx", "--mock"])
    assert exc.value.code == 2


def test_cli_rejects_bad_repo_target():
    from cartouche.cli import main
    rc = main(["repo", "no-slash", "--mock"])
    assert rc == 2


def test_cli_repo_annotations_file_overrides_auto(tmp_path):
    """Custom annotations replace the auto-detected first-star + spike pair."""
    from cartouche.cli import main
    overlay = tmp_path / "events.json"
    overlay.write_text(json.dumps([
        {"date": "2025-12-15",
         "label_top": "// HACKER NEWS", "label_bottom": "// front page"},
        {"date": "2026-04-01",
         "label_top": "// SHIPPED v1", "label_bottom": "// public release"},
    ]))
    out_path = tmp_path / "out.svg"
    rc = main([
        "repo", "Sandjab/Athanor",
        "--annotations-file", str(overlay),
        "--out", str(out_path),
        "--mock",
    ])
    assert rc == 0
    content = out_path.read_text()
    assert "HACKER NEWS" in content
    assert "SHIPPED v1" in content
    # Auto-detected labels should NOT appear once overridden
    assert "FIRST STAR" not in content


def test_cli_repo_annotations_file_count_interpolated(tmp_path):
    """Annotations without explicit `count` get one derived from star_history."""
    from cartouche.cli import _load_annotations_overlay
    history = [
        {"date": "2025-09-01", "count": 0},
        {"date": "2025-12-01", "count": 5},
        {"date": "2026-03-01", "count": 12},
    ]
    overlay_path = tmp_path / "events.json"
    overlay_path.write_text(json.dumps([
        # Date between Dec and Mar: count should be 5 (latest ≤ target)
        {"date": "2026-01-15", "label_top": "X", "label_bottom": "Y"},
    ]))
    result = _load_annotations_overlay(str(overlay_path), history)
    assert len(result) == 1
    assert result[0]["count"] == 5


def test_cli_repo_annotations_file_not_found():
    from cartouche.cli import main
    with pytest.raises(SystemExit) as exc:
        main([
            "repo", "Sandjab/Athanor",
            "--annotations-file", "/nonexistent/path.json",
            "--mock",
        ])
    assert exc.value.code == 2


def test_cli_repo_annotations_file_invalid_json(tmp_path):
    from cartouche.cli import main
    bad = tmp_path / "broken.json"
    bad.write_text("[ this is not json ]")
    with pytest.raises(SystemExit) as exc:
        main([
            "repo", "Sandjab/Athanor",
            "--annotations-file", str(bad),
            "--mock",
        ])
    assert exc.value.code == 2


def test_annotations_layout_descends_on_collision():
    """Two close-X annotations on the right half (sx > 480, so the opposite
    anchor would run off-chart) collide on the default track; the second
    must descend to a lower track while staying inside the FIG. 01 ↔
    x-axis band."""
    from datetime import date

    from cartouche.render.repo import _layout_annotations

    def project(x_data, _count):
        # Both sx > 480 → primary anchor is "end". Opposite "start" would
        # push the long label off the right edge, so flipping isn't an option
        # and the layout has to drop a track. Tight x-spacing forces a
        # horizontal label-box overlap on the default track.
        return 500 + x_data * 1, 200

    start = date(2025, 9, 1)
    anns = [
        {"date": "2025-09-01", "count": 0,
         "label_top": "// VERY LONG LABEL FIRST EVENT", "label_bottom": "// extra detail one"},
        {"date": "2025-10-01", "count": 5,
         "label_top": "// VERY LONG LABEL SECOND EVENT", "label_bottom": "// extra detail two"},
    ]
    placed = _layout_annotations(anns, project, start)
    assert len(placed) == 2
    # Earlier annotation is at base track; later one descends.
    assert placed[0]["leader_y"] < placed[1]["leader_y"]
    # Both stay in the band between FIG. 01 (124) and the x-axis (320).
    for p in placed:
        assert 124 < p["leader_y"] < 320


def test_annotations_layout_monotone_y():
    """Y is monotonically non-decreasing in date order — leftmost (earliest)
    annotation is always at or above any later one. Three annotations
    cramped on the right half so the staircase has to descend twice."""
    from datetime import date

    from cartouche.render.repo import _layout_annotations

    def project(x_data, _count):
        # All sx > 480 → can't flip to the left without going off-chart.
        return 500 + x_data * 8, 200

    start = date(2025, 9, 1)
    long_top = "// LONG TITLE THAT NEEDS ROOM"
    long_bot = "// long descriptive subtext"
    anns = [
        {"date": f"2025-09-{day:02d}", "count": i,
         "label_top": long_top, "label_bottom": long_bot}
        for i, day in enumerate([1, 5, 9], start=1)
    ]
    placed = _layout_annotations(anns, project, start)
    ys = [p["leader_y"] for p in placed]
    # Strictly monotone descending: each later annotation pushed lower.
    assert ys[0] < ys[1] < ys[2]


def test_annotations_layout_preserves_date_order():
    """Output is sorted by date regardless of input order."""
    from datetime import date

    from cartouche.render.repo import _layout_annotations

    def project(x_data, _count):
        return 100 + x_data * 2, 200

    start = date(2025, 9, 1)
    anns = [
        {"date": "2026-04-01", "count": 20, "label_top": "// LATE", "label_bottom": "// later"},
        {"date": "2025-10-01", "count": 5,  "label_top": "// EARLY", "label_bottom": "// earlier"},
    ]
    placed = _layout_annotations(anns, project, start)
    assert [p["date"] for p in placed] == ["2025-10-01", "2026-04-01"]


def test_cli_repo_annotations_file_missing_required_key(tmp_path):
    from cartouche.cli import main
    overlay = tmp_path / "events.json"
    overlay.write_text(json.dumps([
        {"date": "2026-01-01"},  # missing label_top + label_bottom
    ]))
    with pytest.raises(SystemExit) as exc:
        main([
            "repo", "Sandjab/Athanor",
            "--annotations-file", str(overlay),
            "--mock",
        ])
    assert exc.value.code == 2


# ──────────────────────────────────────────────────────────────────────────
#  Notes block — word-wrap and ellipsis truncation
# ──────────────────────────────────────────────────────────────────────────

def test_wrap_note_short_fits_single_line():
    from cartouche.render.primitives import _wrap_note
    lines = _wrap_note("Hello world", w_first=40, w_cont=40, max_lines=2)
    assert lines == ["Hello world"]


def test_wrap_note_wraps_at_word_boundary():
    """Long input wraps to a 2nd line without splitting any word."""
    from cartouche.render.primitives import _wrap_note
    src = "alpha beta gamma delta epsilon"
    lines = _wrap_note(src, w_first=20, w_cont=20, max_lines=2)
    assert lines == ["alpha beta gamma", "delta epsilon"]
    # No word was split; rejoining recovers the original input verbatim.
    assert " ".join(lines) == src


def test_wrap_note_truncates_with_ellipsis_when_overflow():
    """When the text exceeds max_lines lines, the last line ends with '…'."""
    from cartouche.render.primitives import _wrap_note
    lines = _wrap_note(
        "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
        w_first=12, w_cont=12, max_lines=2,
    )
    assert len(lines) == 2
    assert lines[-1].endswith("…")


def test_notes_block_renders_at_8pt():
    """notes_block emits its bullet rows at the smaller 8pt size, not the
    default 9pt of role='dim', so they're less likely to crash into the
    cartouche on the right."""
    from cartouche.render import primitives as P
    lang = lang_module.load("en")
    theme = get_theme("blueprint-light")
    svg = P.notes_block(["short note"], 40, 824, theme, lang)
    assert 'font-size="8"' in svg
    # The label header above the bullets stays at the role default (10).
    assert 'font-size="10"' in svg


def test_profile_canvas_height_is_912():
    """Layout doc and CANVAS_H must agree (sanity guard against silent
    drift if someone tweaks one and forgets the other)."""
    from cartouche.render import profile as P
    assert P.CANVAS_H == 912
    # The viewBox in the produced SVG must reflect that.
    svg = P.render(mock_profile(), get_theme("blueprint-light"),
                   lang_module.load("en"))
    assert 'viewBox="0 0 680 912"' in svg
