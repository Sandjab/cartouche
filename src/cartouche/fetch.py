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
import warnings
from collections import Counter
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import __version__
from . import lang as _lang_module
from .cache import Cache
from .lang import tmpl

API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
# Derived from the package version so it tracks releases automatically;
# GitHub doesn't enforce anything specific, but a sensible UA helps when
# debugging rate-limit traces in their server logs.
USER_AGENT = f"cartouche-svg/{__version__}"

# A GitHub-safe identifier: alphanumeric plus `.`, `_`, `-`, leading alnum,
# 1..100 chars. Tighter than what GitHub allows but a superset of every
# real owner/repo/handle. Used to fail fast on user-supplied segments
# before they reach an interpolated f-string URL — defense-in-depth
# against URL/query smuggling.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _validate_segment(kind: str, value: str) -> str:
    """Return `value` if it matches `_SEGMENT_RE`, else raise ValueError.

    The regex is intentionally stricter than GitHub itself (which allows
    a few exotic edge cases for grandfathered names). On top of the regex,
    we also reject `..` substrings and trailing `.` / `-`: those don't
    enable URL smuggling against the GitHub REST/GraphQL API today, but
    they make filenames awkward if the value ever reaches a path-building
    callsite (e.g. the cache), and they're never legitimate identifiers.
    """
    if not isinstance(value, str) or not _SEGMENT_RE.match(value):
        raise ValueError(
            f"invalid {kind} {value!r}: expected a GitHub-safe identifier "
            f"(alphanumeric plus . _ -, 1..100 chars, leading alphanumeric)"
        )
    if ".." in value or value.endswith(".") or value.endswith("-"):
        raise ValueError(f"invalid {kind} {value!r}: must not contain '..' or end with '.' or '-'")
    return value


# ──────────────────────────────────────────────────────────────────────────
#  Public entry points
# ──────────────────────────────────────────────────────────────────────────


def repo_data(
    owner: str,
    name: str,
    token: str | None = None,
    lang: dict | None = None,
    cache: Cache | None = None,
) -> dict:
    """Fetch and aggregate everything needed for the repo dashboard.

    `lang` is a language pack (see cartouche.lang). Defaults to English.
    Used to format annotation labels and auto-generated notes.

    `cache` is a `cartouche.cache.Cache`. The two heaviest calls
    (stargazer timeline + language byte counts) are read from / written
    to it; everything else still hits the API. Pass `Cache(enabled=False)`
    to disable, or omit for a default 24h-TTL disk cache.
    """
    if lang is None:
        lang = _lang_module.load("en")
    if cache is None:
        cache = Cache()
    owner = _validate_segment("owner", owner)
    name = _validate_segment("repo name", name)
    token = _resolve_token(token)
    repo = _get_json(f"{API_BASE}/repos/{owner}/{name}", token)

    # Star history (timestamps via the star+json media type) — cached.
    star_dates = _cached_stargazer_dates(owner, name, token, cache)
    star_history = _build_cumulative_history(star_dates)

    # Languages (returns {name: bytes}) — cached.
    lang_bytes = _cached_languages(owner, name, token, cache)
    languages = _bytes_to_pct(lang_bytes)

    # Closed issues — use search to count without paginating all of them.
    # `is:issue` excludes PRs which the issues endpoint conflates.
    closed = _count_search(
        f"repo:{owner}/{name} is:issue is:closed",
        token,
    )

    # Commit counts: 30-day window via paginated /commits + total via stats endpoint.
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    commits_30d = _count_via_pagination(
        f"{API_BASE}/repos/{owner}/{name}/commits?since={since}&per_page=100",
        token,
    )
    commits_total = _count_via_pagination(
        f"{API_BASE}/repos/{owner}/{name}/commits?per_page=100",
        token,
    )

    # Stars/forks delta over 30 days: rough estimate from the cumulative curve.
    today = date.today()
    cutoff = today - timedelta(days=30)
    stars_30d_delta = _delta_since(star_history, cutoff)

    # File-tree based counts for the tests/docs radar axes. One Git Tree
    # call against the default branch — deterministic, in contrast to the
    # Code Search–based estimation that preceded this and oscillated
    # between real counts and 0 because the search index lags behind
    # recent commits and 5xx-s were silently swallowed as 0.
    try:
        counts = _tree_file_counts(owner, name, repo["default_branch"], token)
    except urllib.error.HTTPError as exc:
        warnings.warn(
            f"cartouche: git/trees failed for {owner}/{name} "
            f"(HTTP {exc.code}); tests/docs ratios fall back to 0",
            RuntimeWarning,
            stacklevel=2,
        )
        counts = {"code": 0, "tests": 0, "md": 0}

    # Radar values (normalized 0..1 with reasonable caps for small repos)
    radar = {
        "stars": min(1.0, repo["stargazers_count"] / 100),
        "forks": min(1.0, repo["forks_count"] / 30),
        "commits": min(1.0, commits_30d / 100),
        "code": min(1.0, sum(lang_bytes.values()) / 500_000),
        "tests": _tests_axis(counts["tests"], counts["code"]),
        "docs": min(1.0, counts["md"] / 8),
    }

    return {
        "owner": owner,
        "name": name,
        "stars": repo["stargazers_count"],
        "forks": repo["forks_count"],
        "open_issues": repo["open_issues_count"],
        "closed_issues": closed,
        "commits_30d": commits_30d,
        "commits_total": commits_total,
        "stars_30d_delta": stars_30d_delta,
        "forks_30d_delta": 0,  # GitHub doesn't expose fork timestamps cheaply
        "languages": languages,
        "star_history": star_history,
        "annotations": _detect_annotations(star_history, lang),
        "radar": radar,
        "notes": _build_notes_repo(repo, languages, lang),
        "rev": _next_rev(),
        "date": today.isoformat(),
        "drawn_by": owner,
    }


def profile_data(
    handle: str, token: str | None = None, lang: dict | None = None, cache: Cache | None = None
) -> dict:
    """Fetch and aggregate everything needed for the profile dashboard.

    `lang` defaults to English; used to format auto-generated notes.
    `cache` shares the same disk store used by `repo_data` — the per-repo
    stargazer and language calls (the dominant cost on viral profiles)
    are read through it.
    """
    if lang is None:
        lang = _lang_module.load("en")
    if cache is None:
        cache = Cache()
    handle = _validate_segment("handle", handle)
    token = _resolve_token(token)
    user = _get_json(f"{API_BASE}/users/{handle}", token)

    # All public repos (paginated)
    repos = list(
        _get_paginated(
            f"{API_BASE}/users/{handle}/repos?per_page=100&sort=updated",
            token,
        )
    )
    # Filter out forks for top-5; full list still informs totals.
    # Drop any repo whose name (from the API) doesn't match our segment
    # regex — paranoid, but cheap, and keeps every f-string URL safe.
    own_repos = [r for r in repos if not r["fork"] and _SEGMENT_RE.match(r["name"] or "")]

    # Aggregate star history across all owned repos — cached per repo.
    all_star_dates: list[date] = []
    for r in own_repos:
        if r["stargazers_count"] == 0:
            continue
        repo_name = r["name"]
        try:
            all_star_dates.extend(
                _cached_stargazer_dates(
                    handle,
                    repo_name,
                    token,
                    cache,
                    max_pages=5,
                )
            )
        except urllib.error.HTTPError as exc:
            # Skip this repo, but never silently: a swallowed error here
            # collapses the whole profile star history to an empty chart with
            # no trace. The 403 case is the common one — a GitHub App
            # installation token (e.g. the default Actions GITHUB_TOKEN) gets
            # "Resource not accessible by integration" on cross-repo
            # /stargazers reads and can't aggregate them.
            hint = (
                " — an installation token (e.g. the default Actions "
                "GITHUB_TOKEN) can't read another repo's stargazers; use a PAT"
                if exc.code == 403
                else ""
            )
            warnings.warn(
                f"cartouche: stargazers fetch failed for {handle}/{repo_name} "
                f"(HTTP {exc.code}); its stars are omitted from the profile "
                f"star history{hint}",
                RuntimeWarning,
                stacklevel=2,
            )
            continue
    star_history = _build_cumulative_history(sorted(all_star_dates))

    # Top 5 repos by stars
    top_sorted = sorted(own_repos, key=lambda r: r["stargazers_count"], reverse=True)[:5]
    top_repos = []
    since_iso = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in top_sorted:
        repo_name = _validate_segment("repo name", r["name"])
        commits_30d = _count_via_pagination(
            f"{API_BASE}/repos/{handle}/{repo_name}/commits?per_page=100&since={since_iso}",
            token,
        )
        top_repos.append(
            {
                "name": r["name"],
                "stars": r["stargazers_count"],
                "language": r["language"] or "—",
                "commits_30d": commits_30d,
            }
        )

    # Aggregate languages — cached per repo. `lang_totals` (raw bytes) still
    # feeds the radar's depth/polyglot axes, but the *displayed* stack is
    # equal-weighted per repo (see _languages_equal_weight) so one repo holding
    # a huge vendored/archived blob can't dominate the mix.
    lang_totals: Counter[str] = Counter()
    per_repo_langs: list[dict[str, int]] = []
    for r in own_repos[:20]:  # cap at 20 to stay reasonable
        try:
            repo_langs = _cached_languages(handle, r["name"], token, cache)
        except urllib.error.HTTPError:
            continue
        lang_totals.update(repo_langs)
        per_repo_langs.append(repo_langs)
    languages = _languages_equal_weight(per_repo_langs)

    # Contribution heatmap (GraphQL)
    heatmap, total_contribs, total_commits_year, restricted_contribs = _fetch_contribution_calendar(
        handle, token
    )

    # Totals
    total_stars = sum(r["stargazers_count"] for r in own_repos)
    total_forks = sum(r["forks_count"] for r in own_repos)

    radar = {
        "reach": min(1.0, user["followers"] / 200),
        "activity": min(1.0, total_commits_year / 1500),
        "breadth": min(1.0, len(own_repos) / 30),
        "depth": min(1.0, sum(lang_totals.values()) / 5_000_000),
        "polyglot": min(1.0, len(lang_totals) / 8),
        "engagement": min(1.0, total_contribs / 2000),
    }

    return {
        "handle": handle,
        "name": user.get("name") or handle,
        "bio": user.get("bio") or "GITHUB PROFILE TELEMETRY",
        "joined": user["created_at"][:10],
        "followers": user["followers"],
        "following": user["following"],
        # Mirror GitHub's headline count (public repos *including* forks).
        # `own_repos` (forks filtered out) still drives the stars / top-5 /
        # stack aggregations, but the displayed repo count matches the profile
        # page so the dashboard doesn't look like it's "missing" repos.
        "public_repos": user["public_repos"],
        "total_stars": total_stars,
        "total_forks": total_forks,
        "total_commits_year": total_commits_year,
        "restricted_contribs": restricted_contribs,
        "languages": languages,
        "star_history": star_history,
        "top_repos": top_repos,
        "contribution_heatmap": heatmap,
        "radar": radar,
        "notes": _build_notes_profile(
            user, own_repos, total_stars, total_commits_year, languages, lang
        ),
        "rev": _next_rev(),
        "date": date.today().isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────────
#  Cached fetchers (the two hot paths)
# ──────────────────────────────────────────────────────────────────────────


def _cached_stargazer_dates(
    owner: str, name: str, token: str | None, cache: Cache, max_pages: int = 50
) -> list[date]:
    """Return the list of star event dates for a repo, using the cache.

    The full, untrimmed list of dates is what we cache (as ISO strings),
    not the downsampled `star_history`. This keeps the cache resilient
    to changes in the downsampling logic and lets the same cache feed
    both `repo_data` (full curve) and `profile_data` (sum across repos).
    """
    owner = _validate_segment("owner", owner)
    name = _validate_segment("repo name", name)
    key = ("stargazers", owner, name)
    cached = cache.get(key)
    if cached is not None:
        return [date.fromisoformat(d) for d in cached]

    pages = _get_paginated(
        f"{API_BASE}/repos/{owner}/{name}/stargazers",
        token,
        accept="application/vnd.github.star+json",
        max_pages=max_pages,
    )
    dates = [_parse_iso(s["starred_at"]) for s in pages]
    cache.put(key, [d.isoformat() for d in dates])
    return dates


def _cached_languages(owner: str, name: str, token: str | None, cache: Cache) -> dict[str, int]:
    """Return the {language: bytes} mapping for a repo, using the cache."""
    owner = _validate_segment("owner", owner)
    name = _validate_segment("repo name", name)
    key = ("languages", owner, name)
    cached = cache.get(key)
    if cached is not None:
        return cached
    data = _get_json(f"{API_BASE}/repos/{owner}/{name}/languages", token)
    cache.put(key, data)
    return data


# ──────────────────────────────────────────────────────────────────────────
#  HTTP helpers
# ──────────────────────────────────────────────────────────────────────────


def _resolve_token(token: str | None) -> str | None:
    return token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


class RateLimitError(RuntimeError):
    """Raised when GitHub returns 403/429 with `X-RateLimit-Remaining: 0`.

    Distinct from a generic HTTPError so callers (and end users via the
    CLI) get a message that says *what to do* — typically "set a token"
    if running anonymous, or "wait until reset" otherwise.
    """


_ALLOWED_HOSTS = frozenset({"api.github.com"})


class _SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Refuse to follow redirects that leave `api.github.com`.

    GitHub's REST and GraphQL endpoints don't issue cross-host redirects in
    normal operation; a redirect anywhere else would mean either a
    misconfigured proxy or an active MITM trying to capture the bearer
    token. urllib's default behavior is to follow the redirect and re-emit
    every header — including `Authorization` — so we must intercept BEFORE
    the next request is built.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        new_host = urllib.parse.urlsplit(newurl).hostname
        if new_host not in _ALLOWED_HOSTS:
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                f"refusing redirect to non-GitHub host {new_host!r}",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


# Module-level alias so tests can monkeypatch the network layer cleanly
# (`monkeypatch.setattr(fetch, "_urlopen", fake)`) without touching the
# global `urllib.request.urlopen`.
_urlopen = urllib.request.build_opener(_SameHostRedirectHandler()).open


def _request(
    url: str,
    token: str | None,
    accept: str = "application/vnd.github+json",
    method: str = "GET",
    body: bytes | None = None,
) -> tuple[bytes, dict]:
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
    try:
        with _urlopen(req, timeout=30) as resp:
            return resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429) and (e.headers.get("X-RateLimit-Remaining") == "0"):
            raise _rate_limit_error(e, has_token=token is not None) from e
        # Re-raise with the endpoint embedded in the message. Otherwise an
        # intermittent 4xx surfaces in CLI output as a bare "HTTP Error 401:
        # Unauthorized" with no way to tell which endpoint flaked. Same
        # class, so callers that catch HTTPError + read `.code` (e.g.
        # `_tree_file_counts` in `repo_data`) keep working.
        raise urllib.error.HTTPError(
            url, e.code, f"{e.reason} ({method} {url})", e.headers, None
        ) from e


def _rate_limit_error(err: urllib.error.HTTPError, *, has_token: bool) -> RateLimitError:
    """Build an actionable RateLimitError from an HTTPError + its headers."""
    parts = ["GitHub API rate limit exceeded"]
    reset = err.headers.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        reset_at = datetime.fromtimestamp(int(reset), tz=timezone.utc)
        wait_min = max(
            0,
            int((reset_at - datetime.now(timezone.utc)).total_seconds() / 60) + 1,
        )
        parts.append(f"resets in ~{wait_min} min ({reset_at.strftime('%H:%M UTC')})")
    if not has_token:
        parts.append("Set GITHUB_TOKEN or pass --token to raise the limit from 60/h to 5000/h.")
    return RateLimitError(" — ".join(parts))


def _get_json(url: str, token: str | None, accept: str = "application/vnd.github+json") -> Any:
    data, _ = _request(url, token, accept=accept)
    return json.loads(data)


def _get_paginated(
    url: str, token: str | None, accept: str = "application/vnd.github+json", max_pages: int = 50
) -> Iterator[dict]:
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


def _is_allowed_host(url: str) -> bool:
    """Return True iff `url` resolves to a host inside `_ALLOWED_HOSTS`.

    Used to fence Link-header-driven follow-ups: GitHub's REST endpoints
    return RFC 5988 `Link: <next-url>; rel="next"` headers, and we must
    not blindly forward those to `_request` — a compromised CDN, MITM,
    or rogue mirror could splice in a `<https://attacker.example/...>`
    URL and harvest the `Authorization: Bearer …` header on the next
    hop. `_SameHostRedirectHandler` only intercepts HTTP redirects, not
    direct requests built from response bodies / headers, so the check
    has to live here too.
    """
    try:
        return urllib.parse.urlsplit(url).hostname in _ALLOWED_HOSTS
    except ValueError:
        return False


def _parse_next_link(header: str) -> str | None:
    m = _LINK_RE.search(header)
    if not m:
        return None
    next_url = m.group(1)
    return next_url if _is_allowed_host(next_url) else None


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
        # Same fence as `_parse_next_link`: a smuggled `rel="last"` URL
        # pointing off-host must not leak the bearer token.
        if not _is_allowed_host(last_url):
            return len(items)
        page_match = re.search(r"[?&]page=(\d+)", last_url)
        per_page_match = re.search(r"[?&]per_page=(\d+)", url)
        if not page_match or not per_page_match:
            return len(items)
        last_page = int(page_match.group(1))
        # We have all items on page 1; need to fetch the last page to know its size.
        last_data, _ = _request(last_url, token)
        last_items = json.loads(last_data)
        per_page = int(per_page_match.group(1))
        return (last_page - 1) * per_page + len(last_items)
    return len(items)


def _count_search(query: str, token: str | None) -> int:
    """Count via the search API, which returns total_count without paginating."""
    encoded = urllib.parse.quote(query)
    data = _get_json(f"{API_BASE}/search/issues?q={encoded}&per_page=1", token)
    return data.get("total_count", 0)


def _post_graphql(query: str, token: str | None, variables: dict | None = None) -> dict:
    """POST a GraphQL query, with optional `variables` passed alongside.

    Always pass user-controlled values via `variables` rather than splicing
    them into the query string — string interpolation in a GraphQL document
    is the GraphQL equivalent of SQL injection (alias smuggling, complexity
    DoS, type confusion).
    """
    if not token:
        raise RuntimeError(
            "GraphQL contribution calendar requires a token; set GITHUB_TOKEN or pass --token."
        )
    payload = {"query": query}
    if variables is not None:
        payload["variables"] = variables
    body = json.dumps(payload).encode("utf-8")
    data, _ = _request(GRAPHQL_URL, token, method="POST", body=body)
    response = json.loads(data)
    if "errors" in response:
        raise RuntimeError(f"GraphQL errors: {response['errors']}")
    return response["data"]


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
    return [
        (name, 100 * b / total)
        for name, b in sorted(lang_bytes.items(), key=lambda kv: kv[1], reverse=True)
    ]


def _languages_equal_weight(per_repo: list[dict[str, int]]) -> list[tuple[str, float]]:
    """Aggregate a profile's languages as the mean of each repo's own breakdown.

    Each repo is normalized to its internal percentages first, then those
    percentages are averaged with EQUAL weight across repos. The effect: one
    repo holding a gigabyte of a single language (a vendored or archived blob
    that GitHub Linguist still counts as source) gets exactly one vote instead
    of swamping the total. This is what keeps a mostly-Python profile from
    reporting "HTML 83%" because of a single repo full of committed HTML.

    Returns the top-10 languages as (name, percent) pairs sorted descending;
    percentages of a full breakdown sum to ~100. Repos with no detected
    language (empty dict) or zero total bytes are skipped, not counted as a
    vote — counting them would dilute every percentage.
    """
    contributing = [d for d in per_repo if sum(d.values()) > 0]
    if not contributing:
        return []
    acc: dict[str, float] = {}
    for d in contributing:
        total = sum(d.values())
        for name, byte_count in d.items():
            acc[name] = acc.get(name, 0.0) + byte_count / total
    n = len(contributing)
    pct = sorted(
        ((name, 100 * share / n) for name, share in acc.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )
    return pct[:10]


def _delta_since(history: list[dict], cutoff: date) -> int:
    """How many stars were added since `cutoff` based on the downsampled history."""
    if not history:
        return 0
    final = history[-1]["count"]
    earlier = next(
        (
            h["count"]
            for h in reversed(history)
            if datetime.strptime(h["date"], "%Y-%m-%d").date() <= cutoff
        ),
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
        annotations.append(
            {
                "date": first_nonzero["date"],
                "count": first_nonzero["count"],
                "label_top": tmpl(lang, "first_star_top", date=first_nonzero["date"]),
                "label_bottom": tmpl(lang, "first_star_bottom"),
            }
        )
    # Largest single-step spike
    deltas = [
        (history[i]["count"] - history[i - 1]["count"], history[i]) for i in range(1, len(history))
    ]
    # Sort by delta only; tuples with equal deltas would otherwise fall through
    # to comparing the dict payloads, which raises TypeError on Python 3.
    deltas.sort(key=lambda d: d[0], reverse=True)
    if deltas and deltas[0][0] >= 3:
        delta, h = deltas[0]
        annotations.append(
            {
                "date": h["date"],
                "count": h["count"],
                "label_top": tmpl(lang, "spike_top", n=delta),
                "label_bottom": tmpl(lang, "spike_bottom", date=h["date"]),
            }
        )
    return annotations


# ──────────────────────────────────────────────────────────────────────────
#  File classification for the repo radar's code / tests axes
# ──────────────────────────────────────────────────────────────────────────

# Source-file extensions (no leading dot) used as the language-agnostic
# denominator of the `tests` density axis. Markdown is handled separately
# (docs axis); config/data/asset formats are excluded on purpose. Adding a
# language is a one-line edit here.
CODE_EXTENSIONS = frozenset(
    {
        "py",
        "pyi",
        "pyx",
        "swift",
        "go",
        "rs",
        "js",
        "jsx",
        "mjs",
        "cjs",
        "ts",
        "tsx",
        "mts",
        "cts",
        "java",
        "kt",
        "kts",
        "scala",
        "sc",
        "rb",
        "php",
        "c",
        "h",
        "cc",
        "cpp",
        "cxx",
        "hpp",
        "hh",
        "hxx",
        "cs",
        "m",
        "mm",
        "dart",
        "ex",
        "exs",
        "erl",
        "hrl",
        "clj",
        "cljs",
        "cljc",
        "hs",
        "lua",
        "sh",
        "bash",
        "zsh",
        "pl",
        "pm",
        "r",
        "jl",
        "groovy",
        "gradle",
        "vue",
        "svelte",
        "fs",
        "fsx",
        "ml",
        "mli",
        "nim",
        "zig",
    }
)

# Directory segments that mark a test tree (matched case-insensitively, so
# SwiftPM's `Tests/` and JS `__tests__/` both count).
TEST_DIR_SEGMENTS = frozenset({"test", "tests", "spec", "specs", "__tests__"})

# Name conventions. The mandatory boundary (`_` `.` `-`, or an uppercase
# letter) is what rejects false positives like `greatest`, `contest`,
# `latest`, `manifest`. `_SNAKE_DOT_TEST_RE` runs on the lowercased stem;
# `_CAMEL_TEST_RE` runs on the original stem to require a CamelCase boundary.
_SNAKE_DOT_TEST_RE = re.compile(r"[._-](?:test|spec)s?$")
_CAMEL_TEST_RE = re.compile(r"[a-z0-9](?:Test|Tests|Spec|Specs)$")


def _is_test_path(segs: list[str], stem: str) -> bool:
    """True if a code file looks like a test, by directory or by name.

    `segs` is the path split on '/'; `stem` is the basename without its
    extension. Directory match wins first (any parent segment is a test
    dir), then the name conventions.
    """
    if any(s.lower() in TEST_DIR_SEGMENTS for s in segs[:-1]):
        return True
    sl = stem.lower()
    if sl in ("test", "tests", "spec", "specs"):
        return True
    if sl.startswith("test_"):
        return True
    if _SNAKE_DOT_TEST_RE.search(sl):
        return True
    if _CAMEL_TEST_RE.search(stem):
        return True
    return False


def _tests_axis(test_count: int, code_count: int) -> float:
    """Repo radar `tests` axis: a density proxy of test files relative to
    code files, saturating at a 30% ratio. Zero when no recognized code
    exists (avoids division by zero; 'no code' → 'no test signal')."""
    if not code_count:
        return 0.0
    return min(1.0, test_count / max(1, code_count * 0.3))


def _tree_file_counts(owner: str, name: str, branch: str, token: str | None) -> dict[str, int]:
    """Count code, test, and Markdown files at the tip of `branch`.

    One recursive Git Tree call, feeding the repo radar's `tests` and `docs`
    axes. Replaces the Code Search–based estimators that preceded this: the
    search index lags fresh commits and rate-limits aggressively, and the
    old code silently treated every error as 0.

    Returns a dict with keys "code", "tests", "md".

    Classification is language-agnostic:
      - basename ending in `.md`                 → "md"
      - extension in `CODE_EXTENSIONS`           → "code", and additionally
        "tests" when `_is_test_path` matches (a test directory, or a name
        convention such as `test_*`, `*_test`, `*.spec`, `FooTests`)
      - anything else (configs, assets, …)       → ignored

    For very large repos (>100k entries) the Git Tree API truncates its
    response; we emit a `RuntimeWarning` and return the counts seen so
    far, which are then lower bounds rather than exact values.
    """
    safe_branch = urllib.parse.quote(branch, safe="")
    url = f"{API_BASE}/repos/{owner}/{name}/git/trees/{safe_branch}?recursive=1"
    data = _get_json(url, token)

    counts = {"code": 0, "tests": 0, "md": 0}
    for entry in data.get("tree", []):
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        segs = path.split("/")
        basename = segs[-1]
        if basename.endswith(".md"):
            counts["md"] += 1
            continue
        dot = basename.rfind(".")
        ext = basename[dot + 1 :].lower() if dot > 0 else ""
        if ext in CODE_EXTENSIONS:
            counts["code"] += 1
            if _is_test_path(segs, basename[:dot]):
                counts["tests"] += 1

    if data.get("truncated"):
        warnings.warn(
            f"cartouche: git tree for {owner}/{name} was truncated; "
            "tests/docs counts are lower bounds",
            RuntimeWarning,
            stacklevel=2,
        )
    return counts


def _fetch_contribution_calendar(
    handle: str,
    token: str | None,
) -> tuple[list[list[int]], int, int, int]:
    """Return (heatmap, total_contribs, total_commits_year, restricted_contribs).

    Heatmap is a 53×7 grid of intensity buckets 0..4. GraphQL returns raw
    counts; we bucket them by quantiles.

    `total_commits_year` is `totalCommitContributions` — *public* commit
    contributions only. `restricted_contribs` is `restrictedContributionsCount`,
    the count of contributions GitHub anonymizes because they happened in
    private repos. The two are surfaced side by side so a profile whose work
    is mostly private isn't misread as low-activity. Note that the restricted
    bucket lumps together private commits, PRs, issues and reviews — it is
    not strictly a private *commit* count. What the querying token can see
    depends on its access: a token that owns the account (or a profile with
    "private contribution counts" made public) returns a non-zero value; an
    anonymous or third-party token typically returns 0.
    """
    query = (
        "query($login: String!) { user(login: $login) { contributionsCollection { "
        "totalCommitContributions "
        "restrictedContributionsCount "
        "contributionCalendar { "
        "totalContributions "
        "weeks { contributionDays { contributionCount weekday } } "
        "} } } }"
    )
    payload = _post_graphql(query, token, variables={"login": handle})
    cc = payload["user"]["contributionsCollection"]
    cal = cc["contributionCalendar"]
    total = cal["totalContributions"]
    total_commits = cc["totalCommitContributions"]
    restricted = cc["restrictedContributionsCount"]

    # Compute thresholds so we have 5 visually distinct buckets
    all_counts = [d["contributionCount"] for w in cal["weeks"] for d in w["contributionDays"]]
    nonzero = sorted(c for c in all_counts if c > 0)
    if nonzero:
        thresholds = [nonzero[int(len(nonzero) * f) - 1] for f in (0.25, 0.5, 0.75, 1.0)]
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

    return heatmap[-53:], total, total_commits, restricted


def _build_notes_repo(repo: dict, languages: list[tuple[str, float]], lang: dict) -> list[str]:
    desc = repo.get("description") or "(no description)"
    lang_summary = " · ".join(f"{n} {p:.0f}%" for n, p in languages[:3])
    notes = [desc]
    if lang_summary:
        notes.append(tmpl(lang, "stack_summary", summary=lang_summary))
    if repo.get("license"):
        notes.append(tmpl(lang, "license_summary", license=repo["license"].get("spdx_id", "?")))
    return notes[:3]


def _build_notes_profile(
    user: dict,
    repos: list[dict],
    total_stars: int,
    total_commits: int,
    languages: list[tuple[str, float]],
    lang: dict,
) -> list[str]:
    notes = [
        tmpl(
            lang,
            "profile_notes_totals",
            # Match the indicator card: GitHub's public-repo count (forks
            # included), not the fork-filtered `repos` used for aggregations.
            n_repos=user["public_repos"],
            n_stars=total_stars,
            n_commits=total_commits,
        ),
    ]
    if languages:
        top3 = " · ".join(f"{n} {p:.0f}%" for n, p in languages[:3])
        notes.append(tmpl(lang, "profile_notes_stack", summary=top3))
    if repos:
        top = max(repos, key=lambda r: r["stargazers_count"])
        notes.append(
            tmpl(
                lang,
                "profile_notes_top",
                name=top["name"],
                stars=top["stargazers_count"],
                description=(top.get("description") or "")[:60],
            )
        )
    return notes[:3]


def _next_rev() -> str:
    """Generate a revision tag from the current date — A.MMDD format."""
    today = date.today()
    return f"{chr(ord('A') + (today.year - 2025) % 26)}.{today.month:02d}{today.day:02d}"
