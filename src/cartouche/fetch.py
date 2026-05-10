"""GitHub API fetchers for Cartouche.

Stdlib only (urllib) — no requests dependency. Returns dicts matching the
shapes consumed by `cartouche.render.repo` and `cartouche.render.profile`,
identical to what `cartouche.mock` produces.

Two entry points:
    repo_data(owner, repo, token=None) -> dict
    profile_data(handle, token=None) -> dict

Token resolution: explicit `token` arg → $GITHUB_TOKEN → $GH_TOKEN → anonymous.
Anonymous requests are rate-limited at 60/h and will fail fast for profiles.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterator

from . import lang as _lang_module
from .lang import tmpl

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
USER_AGENT = "cartouche-svg/0.1"


# ──────────────────────────────────────────────────────────────────────────
#  Public entry points
# ──────────────────────────────────────────────────────────────────────────

def repo_data(owner: str, name: str, token: str | None = None,
              lang: dict | None = None) -> dict:
    """Fetch and aggregate everything needed for the repo dashboard.

    `lang` is a language pack (see cartouche.lang). Defaults to English.
    Used to format annotation labels and auto-generated notes.
    """
    if lang is None:
        lang = _lang_module.load("en")
    token = _resolve_token(token)
    repo = _get_json(f"{API_BASE}/repos/{owner}/{name}", token)

    # Star history (timestamps via the star+json media type)
    stargazers = list(_get_paginated(
        f"{API_BASE}/repos/{owner}/{name}/stargazers",
        token,
        accept="application/vnd.github.star+json",
    ))
    star_history = _build_cumulative_history(
        [_parse_iso(s["starred_at"]) for s in stargazers]
    )

    # Languages (returns {name: bytes})
    lang_bytes = _get_json(f"{API_BASE}/repos/{owner}/{name}/languages", token)
    languages = _bytes_to_pct(lang_bytes)

    # Closed issues — use search to count without paginating all of them.
    # `is:issue` excludes PRs which the issues endpoint conflates.
    closed = _count_search(
        f"repo:{owner}/{name} is:issue is:closed", token,
    )

    # Commit counts: 30-day window via paginated /commits + total via stats endpoint.
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits_30d = _count_via_pagination(
        f"{API_BASE}/repos/{owner}/{name}/commits?since={since}&per_page=100",
        token,
    )
    commits_total = _count_via_pagination(
        f"{API_BASE}/repos/{owner}/{name}/commits?per_page=100", token,
    )

    # Stars/forks delta over 30 days: rough estimate from the cumulative curve.
    today = date.today()
    cutoff = today - timedelta(days=30)
    stars_30d_delta = _delta_since(star_history, cutoff)

    # Radar values (normalized 0..1 with reasonable caps for small repos)
    radar = {
        "stars":   min(1.0, repo["stargazers_count"] / 100),
        "forks":   min(1.0, repo["forks_count"] / 30),
        "commits": min(1.0, commits_30d / 100),
        "code":    min(1.0, sum(lang_bytes.values()) / 500_000),
        "tests":   _estimate_tests_ratio(owner, name, token),
        "docs":    _estimate_docs_ratio(owner, name, token),
    }

    return {
        "owner":            owner,
        "name":             name,
        "stars":            repo["stargazers_count"],
        "forks":            repo["forks_count"],
        "open_issues":      repo["open_issues_count"],
        "closed_issues":    closed,
        "commits_30d":      commits_30d,
        "commits_total":    commits_total,
        "stars_30d_delta":  stars_30d_delta,
        "forks_30d_delta":  0,   # GitHub doesn't expose fork timestamps cheaply
        "languages":        languages,
        "star_history":     star_history,
        "annotations":      _detect_annotations(star_history, lang),
        "radar":            radar,
        "notes":            _build_notes_repo(repo, languages, lang),
        "rev":              _next_rev(),
        "date":             today.isoformat(),
        "drawn_by":         owner,
    }


def profile_data(handle: str, token: str | None = None,
                 lang: dict | None = None) -> dict:
    """Fetch and aggregate everything needed for the profile dashboard.

    `lang` defaults to English; used to format auto-generated notes.
    """
    if lang is None:
        lang = _lang_module.load("en")
    token = _resolve_token(token)
    user = _get_json(f"{API_BASE}/users/{handle}", token)

    # All public repos (paginated)
    repos = list(_get_paginated(
        f"{API_BASE}/users/{handle}/repos?per_page=100&sort=updated",
        token,
    ))
    # Filter out forks for top-5; full list still informs totals
    own_repos = [r for r in repos if not r["fork"]]

    # Aggregate star history across all owned repos
    all_star_dates: list[date] = []
    for r in own_repos:
        if r["stargazers_count"] == 0:
            continue
        try:
            stargazers = list(_get_paginated(
                f"{API_BASE}/repos/{handle}/{r['name']}/stargazers",
                token,
                accept="application/vnd.github.star+json",
                max_pages=5,  # cap to avoid runaway on viral repos
            ))
            all_star_dates.extend(_parse_iso(s["starred_at"]) for s in stargazers)
        except urllib.error.HTTPError:
            continue
    star_history = _build_cumulative_history(sorted(all_star_dates))

    # Top 5 repos by stars
    top_sorted = sorted(own_repos, key=lambda r: r["stargazers_count"], reverse=True)[:5]
    top_repos = []
    for r in top_sorted:
        commits_30d = _count_via_pagination(
            f"{API_BASE}/repos/{handle}/{r['name']}/commits?per_page=100"
            f"&since={(datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            token,
        )
        top_repos.append({
            "name":        r["name"],
            "stars":       r["stargazers_count"],
            "language":    r["language"] or "—",
            "commits_30d": commits_30d,
        })

    # Aggregate languages (bytes-weighted)
    lang_totals: Counter[str] = Counter()
    for r in own_repos[:20]:  # cap at 20 to stay reasonable
        try:
            lb = _get_json(f"{API_BASE}/repos/{handle}/{r['name']}/languages", token)
            lang_totals.update(lb)
        except urllib.error.HTTPError:
            continue
    languages = _bytes_to_pct(dict(lang_totals.most_common(10)))

    # Contribution heatmap (GraphQL)
    heatmap, total_contribs, total_commits_year = _fetch_contribution_calendar(
        handle, token,
    )

    # Totals
    total_stars = sum(r["stargazers_count"] for r in own_repos)
    total_forks = sum(r["forks_count"] for r in own_repos)

    radar = {
        "reach":      min(1.0, user["followers"] / 200),
        "activity":   min(1.0, total_commits_year / 1500),
        "breadth":    min(1.0, len(own_repos) / 30),
        "depth":      min(1.0, sum(lang_totals.values()) / 5_000_000),
        "polyglot":   min(1.0, len(lang_totals) / 8),
        "engagement": min(1.0, total_contribs / 2000),
    }

    return {
        "handle":               handle,
        "name":                 user.get("name") or handle,
        "bio":                  user.get("bio") or "GITHUB PROFILE TELEMETRY",
        "joined":               user["created_at"][:10],
        "followers":            user["followers"],
        "following":            user["following"],
        "public_repos":         len(own_repos),
        "total_stars":          total_stars,
        "total_forks":          total_forks,
        "total_commits_year":   total_commits_year,
        "languages":            languages,
        "star_history":         star_history,
        "top_repos":            top_repos,
        "contribution_heatmap": heatmap,
        "radar":                radar,
        "notes":                _build_notes_profile(user, own_repos, total_stars,
                                                    total_commits_year, languages,
                                                    lang),
        "rev":                  _next_rev(),
        "date":                 date.today().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
#  HTTP helpers
# ──────────────────────────────────────────────────────────────────────────

def _resolve_token(token: str | None) -> str | None:
    return token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _request(url: str, token: str | None,
             accept: str = "application/vnd.github+json",
             method: str = "GET", body: bytes | None = None) -> tuple[bytes, dict]:
    headers = {
        "Accept": accept,
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, headers=headers, method=method, data=body)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read(), dict(resp.headers)


def _get_json(url: str, token: str | None,
              accept: str = "application/vnd.github+json") -> Any:
    data, _ = _request(url, token, accept=accept)
    return json.loads(data)


def _get_paginated(url: str, token: str | None,
                   accept: str = "application/vnd.github+json",
                   max_pages: int = 50) -> Iterator[dict]:
    """Yield items from a paginated endpoint, following Link rel="next"."""
    next_url = url
    pages = 0
    while next_url and pages < max_pages:
        data, headers = _request(next_url, token, accept=accept)
        page = json.loads(data)
        if not isinstance(page, list):
            return
        yield from page
        pages += 1
        next_url = _parse_next_link(headers.get("Link", ""))


_LINK_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _parse_next_link(header: str) -> str | None:
    m = _LINK_RE.search(header)
    return m.group(1) if m else None


def _count_via_pagination(url: str, token: str | None) -> int:
    """Count items by reading the `last` page link if present, else iterate."""
    data, headers = _request(url, token)
    items = json.loads(data)
    if not isinstance(items, list):
        return 0
    link = headers.get("Link", "")
    last_match = re.search(r'<([^>]+)>;\s*rel="last"', link)
    if last_match:
        last_url = last_match.group(1)
        last_page = int(re.search(r"[?&]page=(\d+)", last_url).group(1))
        # We have all items on page 1; need to fetch the last page to know its size.
        last_data, _ = _request(last_url, token)
        last_items = json.loads(last_data)
        per_page = int(re.search(r"[?&]per_page=(\d+)", url).group(1))
        return (last_page - 1) * per_page + len(last_items)
    return len(items)


def _count_search(query: str, token: str | None) -> int:
    """Count via the search API, which returns total_count without paginating."""
    encoded = urllib.parse.quote(query)
    data = _get_json(f"{API_BASE}/search/issues?q={encoded}&per_page=1", token)
    return data.get("total_count", 0)


def _post_graphql(query: str, token: str | None) -> dict:
    if not token:
        raise RuntimeError(
            "GraphQL contribution calendar requires a token; "
            "set GITHUB_TOKEN or pass --token."
        )
    body = json.dumps({"query": query}).encode("utf-8")
    data, _ = _request(GRAPHQL_URL, token, method="POST", body=body)
    payload = json.loads(data)
    if "errors" in payload:
        raise RuntimeError(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


# ──────────────────────────────────────────────────────────────────────────
#  Aggregation helpers
# ──────────────────────────────────────────────────────────────────────────

def _parse_iso(s: str) -> date:
    """Parse a GitHub timestamp (UTC, 'Z'-suffixed) to a date."""
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _build_cumulative_history(dates: list[date]) -> list[dict]:
    """Convert a sorted list of star event dates to a downsampled cumulative
    curve. Aim for ~12 control points so the rendered SVG path stays readable.
    """
    if not dates:
        return []
    dates = sorted(dates)
    start, end = dates[0], date.today()
    span_days = max((end - start).days, 1)
    target_points = 12
    step = max(1, span_days // target_points)

    counts: list[tuple[date, int]] = []
    current = start
    cumulative = 0
    i = 0
    while current <= end:
        while i < len(dates) and dates[i] <= current:
            cumulative += 1
            i += 1
        counts.append((current, cumulative))
        current += timedelta(days=step)
    # Always include the final day
    counts.append((end, len(dates)))
    return [{"date": d.isoformat(), "count": c} for d, c in counts]


def _bytes_to_pct(lang_bytes: dict[str, int]) -> list[tuple[str, float]]:
    total = sum(lang_bytes.values())
    if total == 0:
        return []
    return [(name, 100 * b / total) for name, b in
            sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)]


def _delta_since(history: list[dict], cutoff: date) -> int:
    """How many stars were added since `cutoff` based on the downsampled history."""
    if not history:
        return 0
    final = history[-1]["count"]
    earlier = next(
        (h["count"] for h in reversed(history)
         if datetime.strptime(h["date"], "%Y-%m-%d").date() <= cutoff),
        0,
    )
    return max(0, final - earlier)


def _detect_annotations(history: list[dict], lang: dict) -> list[dict]:
    """Mark up to 2 notable events: the first star, and the largest spike.

    Labels are formatted using the lang pack so they translate cleanly.
    """
    if len(history) < 3:
        return []
    annotations = []
    # First star event
    first_nonzero = next((h for h in history if h["count"] > 0), None)
    if first_nonzero:
        annotations.append({
            "date":         first_nonzero["date"],
            "count":        first_nonzero["count"],
            "label_top":    tmpl(lang, "first_star_top",
                                 date=first_nonzero["date"]),
            "label_bottom": tmpl(lang, "first_star_bottom"),
        })
    # Largest single-step spike
    deltas = [(history[i]["count"] - history[i - 1]["count"], history[i])
              for i in range(1, len(history))]
    deltas.sort(reverse=True)
    if deltas and deltas[0][0] >= 3:
        delta, h = deltas[0]
        annotations.append({
            "date":         h["date"],
            "count":        h["count"],
            "label_top":    tmpl(lang, "spike_top", n=delta),
            "label_bottom": tmpl(lang, "spike_bottom", date=h["date"]),
        })
    return annotations


def _estimate_tests_ratio(owner: str, name: str, token: str | None) -> float:
    """Approximate test coverage by file-count ratio: tests/* and test_*.py."""
    try:
        # Use the search endpoint to count test files
        q1 = urllib.parse.quote(f"repo:{owner}/{name} path:tests")
        q2 = urllib.parse.quote(f"repo:{owner}/{name} extension:py")
        tests = _get_json(f"{API_BASE}/search/code?q={q1}&per_page=1", token).get("total_count", 0)
        py = _get_json(f"{API_BASE}/search/code?q={q2}&per_page=1", token).get("total_count", 0)
        if py == 0:
            return 0.0
        return min(1.0, tests / max(1, py * 0.3))
    except urllib.error.HTTPError:
        return 0.0


def _estimate_docs_ratio(owner: str, name: str, token: str | None) -> float:
    """Approximate documentation density by counting .md files."""
    try:
        q = urllib.parse.quote(f"repo:{owner}/{name} extension:md")
        md = _get_json(f"{API_BASE}/search/code?q={q}&per_page=1", token).get("total_count", 0)
        return min(1.0, md / 8)
    except urllib.error.HTTPError:
        return 0.0


def _fetch_contribution_calendar(
    handle: str, token: str | None,
) -> tuple[list[list[int]], int, int]:
    """Return (heatmap, total_contribs, total_commits_year).

    Heatmap is a 53×7 grid of intensity buckets 0..4. GraphQL returns raw
    counts; we bucket them by quantiles.
    """
    query = (
        '{ user(login: "%s") { contributionsCollection { '
        'totalCommitContributions '
        'contributionCalendar { '
        'totalContributions '
        'weeks { contributionDays { contributionCount weekday } } '
        '} } } }' % handle
    )
    payload = _post_graphql(query, token)
    cc = payload["user"]["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total = cal["totalContributions"]
    total_commits = cc["totalCommitContributions"]

    # Compute thresholds so we have 5 visually distinct buckets
    all_counts = [d["contributionCount"]
                  for w in cal["weeks"] for d in w["contributionDays"]]
    nonzero = sorted(c for c in all_counts if c > 0)
    if nonzero:
        thresholds = [
            nonzero[int(len(nonzero) * f) - 1]
            for f in (0.25, 0.5, 0.75, 1.0)
        ]
    else:
        thresholds = [1, 2, 3, 4]

    def bucket(n: int) -> int:
        if n == 0:
            return 0
        for i, t in enumerate(thresholds, start=1):
            if n <= t:
                return i
        return 4

    heatmap: list[list[int]] = []
    for w in cal["weeks"]:
        col = [0] * 7
        for d in w["contributionDays"]:
            col[d["weekday"]] = bucket(d["contributionCount"])
        heatmap.append(col)

    # Pad to 53 columns if GraphQL returned fewer
    while len(heatmap) < 53:
        heatmap.insert(0, [0] * 7)

    return heatmap[-53:], total, total_commits


def _build_notes_repo(repo: dict, languages: list[tuple[str, float]],
                      lang: dict) -> list[str]:
    desc = repo.get("description") or "(no description)"
    lang_summary = " · ".join(f"{n} {p:.0f}%" for n, p in languages[:3])
    notes = [desc]
    if lang_summary:
        notes.append(tmpl(lang, "stack_summary", summary=lang_summary))
    if repo.get("license"):
        notes.append(tmpl(lang, "license_summary",
                          license=repo["license"].get("spdx_id", "?")))
    return notes[:3]


def _build_notes_profile(user: dict, repos: list[dict],
                         total_stars: int, total_commits: int,
                         languages: list[tuple[str, float]],
                         lang: dict) -> list[str]:
    notes = [
        tmpl(lang, "profile_notes_totals",
             n_repos=len(repos),
             n_stars=total_stars,
             n_commits=total_commits),
    ]
    if languages:
        top3 = " · ".join(f"{n} {p:.0f}%" for n, p in languages[:3])
        notes.append(tmpl(lang, "profile_notes_stack", summary=top3))
    if repos:
        top = max(repos, key=lambda r: r["stargazers_count"])
        notes.append(tmpl(lang, "profile_notes_top",
                          name=top["name"],
                          stars=top["stargazers_count"],
                          description=(top.get("description") or "")[:60]))
    return notes[:3]


def _next_rev() -> str:
    """Generate a revision tag from the current date — A.MMDD format."""
    today = date.today()
    return f"{chr(ord('A') + (today.year - 2025) % 26)}.{today.month:02d}{today.day:02d}"
