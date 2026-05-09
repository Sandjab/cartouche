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
