"""Canned data fixtures for testing renderers without hitting the GitHub API.

`mock_repo()` and `mock_profile()` return realistic-shape fixtures whose
text labels (annotations, notes) are formatted using a language pack.
The CLI's `--mock` flag reads from here.

Notes content (the bullet points themselves) are illustrative project
descriptions — they're treated as user-supplied DATA, not labels, so they
remain in the original mock language regardless of the lang pack.
For pure label translation tests, look at how the annotation strings flow.
"""

from __future__ import annotations

from datetime import date, timedelta

from . import lang as _lang_module
from .lang import tmpl


def mock_repo(owner: str = "Sandjab", name: str = "Athanor", lang: dict | None = None) -> dict:
    """Return a plausible repo data fixture: small Python project, ~8 months
    old, 23 stars, with two annotation events (first star + a small spike)."""
    if lang is None:
        lang = _lang_module.load("en")

    start = date(2025, 9, 1)
    counts = [
        (start, 0),
        (start + timedelta(days=37), 1),  # first star event
        (start + timedelta(days=72), 3),
        (start + timedelta(days=110), 7),
        (start + timedelta(days=150), 12),  # post-HN spike
        (start + timedelta(days=158), 18),
        (start + timedelta(days=195), 20),
        (start + timedelta(days=235), 22),
        (start + timedelta(days=250), 23),
    ]
    star_history = [{"date": d.isoformat(), "count": c} for d, c in counts]

    first_date = (start + timedelta(days=37)).isoformat()
    spike_date = (start + timedelta(days=150)).isoformat()

    return {
        "owner": owner,
        "name": name,
        "stars": 23,
        "forks": 4,
        "open_issues": 12,
        "closed_issues": 38,
        "commits_30d": 67,
        "commits_total": 156,
        "stars_30d_delta": 4,
        "forks_30d_delta": 1,
        "languages": [("Python", 87.0), ("TOML", 8.0), ("Markdown", 5.0)],
        "star_history": star_history,
        "annotations": [
            {
                "date": first_date,
                "count": 1,
                "label_top": tmpl(lang, "first_star_top", date=first_date),
                "label_bottom": tmpl(lang, "first_star_bottom"),
            },
            {
                "date": spike_date,
                "count": 12,
                "label_top": tmpl(lang, "spike_top", n=6),
                "label_bottom": tmpl(lang, "spike_bottom", date=spike_date),
            },
        ],
        "radar": {
            "stars": 0.25,
            "forks": 0.15,
            "commits": 0.75,
            "code": 0.60,
            "tests": 0.45,
            "docs": 0.80,
        },
        "notes": [
            "Pipeline: atomic claims → SQLite + embeddings → 3-tier dedup → wiki MD",
            "Canonical docs: CLAUDE.md · ARCHITECTURE.md · SPEC.md",
            "Inspired by Karpathy LLM-Wiki · augmented with claim-level dedup + auto-scoring",
        ],
        "rev": "A.04",
        "date": "2026-05-09",
        "drawn_by": owner,
    }


def mock_profile(handle: str = "Sandjab", lang: dict | None = None) -> dict:
    """Return a plausible profile fixture: ~12 public repos, mid-activity
    developer, ~3 years on GitHub, ~80 followers."""
    if lang is None:
        lang = _lang_module.load("en")

    start = date(2023, 4, 1)
    counts = [
        (start, 0),
        (start + timedelta(days=90), 2),
        (start + timedelta(days=210), 8),
        (start + timedelta(days=340), 23),
        (start + timedelta(days=470), 47),
        (start + timedelta(days=600), 78),
        (start + timedelta(days=720), 112),
        (start + timedelta(days=840), 146),
        (start + timedelta(days=950), 168),
        (start + timedelta(days=1040), 184),
    ]
    star_history = [{"date": d.isoformat(), "count": c} for d, c in counts]

    top_repos = [
        {"name": "athanor", "stars": 23, "language": "Python", "commits_30d": 67},
        {"name": "kabbalah", "stars": 19, "language": "TypeScript", "commits_30d": 12},
        {"name": "mercure-mcp", "stars": 17, "language": "Python", "commits_30d": 4},
        {"name": "cartouche", "stars": 14, "language": "Python", "commits_30d": 88},
        {"name": "apikoltar-corpus", "stars": 12, "language": "Markdown", "commits_30d": 6},
    ]

    # Synthetic 53-week × 7-day contribution heatmap. Values are 0..4 intensity
    # buckets. Sparse start, denser recent weeks.
    heatmap = []
    rng = _seeded(42)
    for week in range(53):
        col = []
        weight = 0.3 + (week / 53) * 0.7
        for _ in range(7):
            r = next(rng)
            if r < 1 - weight:
                col.append(0)
            elif r < 1 - weight + 0.15:
                col.append(1)
            elif r < 1 - weight + 0.30:
                col.append(2)
            elif r < 1 - weight + 0.40:
                col.append(3)
            else:
                col.append(4)
        heatmap.append(col)

    return {
        "handle": handle,
        "name": handle,
        "joined": "2023-04-01",
        "followers": 84,
        "following": 42,
        "public_repos": 12,
        "total_stars": 184,
        "total_forks": 31,
        "total_commits_year": 1247,
        "restricted_contribs": 312,
        "languages": [
            ("Python", 62.0),
            ("TypeScript", 18.0),
            ("Markdown", 12.0),
            ("Other", 8.0),
        ],
        "star_history": star_history,
        "top_repos": top_repos,
        "contribution_heatmap": heatmap,
        "radar": {
            "reach": 0.55,
            "activity": 0.78,
            "breadth": 0.45,
            "depth": 0.60,
            "polyglot": 0.50,
            "engagement": 0.40,
        },
        "bio": "Knowledge compiler, AI policy, French popularization.",
        "notes": [
            tmpl(lang, "profile_notes_totals", n_repos=12, n_stars=184, n_commits=1247),
            tmpl(lang, "profile_notes_stack", summary="Python 62% · TypeScript 18% · Markdown 12%"),
            tmpl(
                lang,
                "profile_notes_top",
                name="athanor",
                stars=23,
                description="knowledge compiler",
            ),
        ],
        "rev": "A.04",
        "date": "2026-05-09",
    }


def _seeded(seed: int):
    """Tiny LCG so the heatmap is deterministic without pulling random."""
    state = seed
    while True:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        yield state / 0x7FFFFFFF
