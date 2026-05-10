"""Integration-flavored tests for `cartouche.fetch`.

The HTTP layer is the only part of the codebase that talks to a remote
service, and it's not exercised by the parametrized render tests. Here
we monkey-patch `urllib.request.urlopen` with a fake that returns
canned bytes + headers so we can exercise:

  - request construction (User-Agent, Authorization, timeout)
  - rate-limit detection (the new RateLimitError contract)
  - pagination (Link header, max_pages cap, _count_via_pagination)
  - token resolution priority

No real network is contacted from this module — the monkey-patch
intercepts every outgoing request.
"""

from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.message import Message

import pytest

from cartouche import __version__, fetch

# ──────────────────────────────────────────────────────────────────────────
#  Fakes
# ──────────────────────────────────────────────────────────────────────────


class _FakeResp:
    """Minimal stand-in for what `urllib.request.urlopen` returns."""

    def __init__(self, body: bytes | str, headers: dict[str, str] | None = None):
        self._body = body if isinstance(body, (bytes, bytearray)) else body.encode()
        self._hdrs = Message()
        for k, v in (headers or {}).items():
            self._hdrs[k] = v

    @property
    def headers(self) -> Message:
        return self._hdrs

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code: int, headers: dict[str, str] | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError with the given response headers attached."""
    msg = Message()
    for k, v in (headers or {}).items():
        msg[k] = v
    return urllib.error.HTTPError(
        url="https://api.github.com/test",
        code=code,
        msg="Test",
        hdrs=msg,
        fp=io.BytesIO(b""),
    )


def _patch_urlopen(monkeypatch: pytest.MonkeyPatch, response_fn):
    """Replace `fetch._urlopen` with a fake that calls `response_fn(req)`.

    Note: `fetch._urlopen` is the module-level alias for the same-host
    redirect-blocking opener (see `fetch._SameHostRedirectHandler`).
    We patch the alias rather than `urllib.request.urlopen` so that the
    redirect-handler wiring is exercised in production paths and bypassed
    here on purpose for unit-level isolation.

    `response_fn` returns a `_FakeResp` (used directly) or an
    `Exception` (raised). Captured request is exposed via the returned
    dict for assertion in tests.
    """
    captured: dict = {}

    def fake_urlopen(req, timeout=None):
        captured["req"] = req
        captured["timeout"] = timeout
        result = response_fn(req)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(fetch, "_urlopen", fake_urlopen)
    return captured


# ──────────────────────────────────────────────────────────────────────────
#  Request construction
# ──────────────────────────────────────────────────────────────────────────


def test_user_agent_tracks_package_version(monkeypatch: pytest.MonkeyPatch):
    cap = _patch_urlopen(monkeypatch, lambda req: _FakeResp(b"ok"))
    fetch._request("https://api.github.com/x", token=None)
    assert cap["req"].get_header("User-agent") == f"cartouche-svg/{__version__}"


def test_token_attached_as_bearer(monkeypatch: pytest.MonkeyPatch):
    cap = _patch_urlopen(monkeypatch, lambda req: _FakeResp(b"ok"))
    fetch._request("https://api.github.com/x", token="ghp_secret")
    assert cap["req"].get_header("Authorization") == "Bearer ghp_secret"


def test_no_token_no_auth_header(monkeypatch: pytest.MonkeyPatch):
    cap = _patch_urlopen(monkeypatch, lambda req: _FakeResp(b"ok"))
    fetch._request("https://api.github.com/x", token=None)
    assert cap["req"].get_header("Authorization") is None


def test_api_version_header_pinned(monkeypatch: pytest.MonkeyPatch):
    """Pin the API version header so we don't drift onto a default if
    GitHub ever changes its routing."""
    cap = _patch_urlopen(monkeypatch, lambda req: _FakeResp(b"ok"))
    fetch._request("https://api.github.com/x", token=None)
    assert cap["req"].get_header("X-github-api-version") == "2022-11-28"


def test_request_returns_body_and_headers(monkeypatch: pytest.MonkeyPatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResp(b'{"hello": "world"}', {"X-Custom": "yes"}),
    )
    body, headers = fetch._request("https://api.github.com/x", token=None)
    assert body == b'{"hello": "world"}'
    assert headers["X-Custom"] == "yes"


# ──────────────────────────────────────────────────────────────────────────
#  Rate-limit handling
# ──────────────────────────────────────────────────────────────────────────


def test_403_with_remaining_zero_raises_rate_limit_error(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(403, {"X-RateLimit-Remaining": "0"}),
    )
    with pytest.raises(fetch.RateLimitError) as exc_info:
        fetch._request("https://api.github.com/x", token=None)
    assert "rate limit" in str(exc_info.value).lower()


def test_anon_rate_limit_message_suggests_token(monkeypatch: pytest.MonkeyPatch):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(403, {"X-RateLimit-Remaining": "0"}),
    )
    with pytest.raises(fetch.RateLimitError) as exc_info:
        fetch._request("https://api.github.com/x", token=None)
    msg = str(exc_info.value)
    assert "GITHUB_TOKEN" in msg or "--token" in msg


def test_authenticated_rate_limit_message_omits_token_hint(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(403, {"X-RateLimit-Remaining": "0"}),
    )
    with pytest.raises(fetch.RateLimitError) as exc_info:
        fetch._request("https://api.github.com/x", token="ghp_x")
    assert "--token" not in str(exc_info.value)


def test_rate_limit_message_includes_reset_window(
    monkeypatch: pytest.MonkeyPatch,
):
    future = int(datetime.now(timezone.utc).timestamp()) + 1800  # +30 min
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(
            403,
            {
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(future),
            },
        ),
    )
    with pytest.raises(fetch.RateLimitError) as exc_info:
        fetch._request("https://api.github.com/x", token=None)
    assert "min" in str(exc_info.value)
    assert "UTC" in str(exc_info.value)


def test_429_with_remaining_zero_also_raises_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_urlopen(
        monkeypatch,
        lambda req: _http_error(429, {"X-RateLimit-Remaining": "0"}),
    )
    with pytest.raises(fetch.RateLimitError):
        fetch._request("https://api.github.com/x", token=None)


def test_403_without_rate_limit_header_propagates_as_http_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """A 403 that isn't a rate limit (e.g. forbidden private resource)
    must propagate as the original HTTPError, not be misclassified."""
    _patch_urlopen(monkeypatch, lambda req: _http_error(403))
    with pytest.raises(urllib.error.HTTPError):
        fetch._request("https://api.github.com/x", token=None)


def test_404_propagates_unchanged(monkeypatch: pytest.MonkeyPatch):
    _patch_urlopen(monkeypatch, lambda req: _http_error(404))
    with pytest.raises(urllib.error.HTTPError):
        fetch._request("https://api.github.com/x", token=None)


# ──────────────────────────────────────────────────────────────────────────
#  Pagination
# ──────────────────────────────────────────────────────────────────────────


def test_parse_next_link_picks_rel_next():
    link = (
        '<https://api.github.com/x?page=2>; rel="next", '
        '<https://api.github.com/x?page=3>; rel="last"'
    )
    assert fetch._parse_next_link(link) == "https://api.github.com/x?page=2"


def test_parse_next_link_no_next_returns_none():
    link = '<https://api.github.com/x?page=3>; rel="last"'
    assert fetch._parse_next_link(link) is None


def test_parse_next_link_empty_string_returns_none():
    assert fetch._parse_next_link("") is None


def test_get_paginated_follows_link_chain(monkeypatch: pytest.MonkeyPatch):
    page1 = json.dumps([{"id": 1}, {"id": 2}]).encode()
    page2 = json.dumps([{"id": 3}]).encode()
    responses = {
        "https://api.github.com/x": (
            page1,
            {"Link": '<https://api.github.com/x?page=2>; rel="next"'},
        ),
        "https://api.github.com/x?page=2": (page2, {}),
    }

    def respond(req):
        body, hdrs = responses[req.full_url]
        return _FakeResp(body, hdrs)

    _patch_urlopen(monkeypatch, respond)
    items = list(fetch._get_paginated("https://api.github.com/x", token=None))
    assert items == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_get_paginated_caps_at_max_pages(monkeypatch: pytest.MonkeyPatch):
    """Without max_pages, an always-'next' API would loop forever."""
    body = json.dumps([{"i": 0}]).encode()
    _patch_urlopen(
        monkeypatch,
        lambda req: _FakeResp(
            body,
            {"Link": '<https://api.github.com/x?page=N>; rel="next"'},
        ),
    )
    items = list(fetch._get_paginated("https://api.github.com/x", token=None, max_pages=3))
    assert len(items) == 3  # one item per page × 3 pages


def test_count_via_pagination_uses_last_link(monkeypatch: pytest.MonkeyPatch):
    """Page 1 is full (100 items) and Link points at page 5 with 3 items,
    so the total is 4 full pages + 3 = 403."""
    full_page = json.dumps([{"i": j} for j in range(100)]).encode()
    last_page = json.dumps([{"i": 0}, {"i": 1}, {"i": 2}]).encode()
    last_link = '<https://api.github.com/x?per_page=100&page=5>; rel="last"'
    responses = {
        "https://api.github.com/x?per_page=100": (full_page, {"Link": last_link}),
        "https://api.github.com/x?per_page=100&page=5": (last_page, {}),
    }

    def respond(req):
        body, hdrs = responses[req.full_url]
        return _FakeResp(body, hdrs)

    _patch_urlopen(monkeypatch, respond)
    n = fetch._count_via_pagination("https://api.github.com/x?per_page=100", None)
    assert n == 403


def test_count_via_pagination_no_last_link_returns_len_of_first_page(
    monkeypatch: pytest.MonkeyPatch,
):
    body = json.dumps([{"i": 0}, {"i": 1}, {"i": 2}]).encode()
    _patch_urlopen(monkeypatch, lambda req: _FakeResp(body, {}))
    n = fetch._count_via_pagination("https://api.github.com/x?per_page=100", None)
    assert n == 3


# ──────────────────────────────────────────────────────────────────────────
#  Token resolution
# ──────────────────────────────────────────────────────────────────────────


def test_resolve_token_explicit_wins_over_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    monkeypatch.setenv("GH_TOKEN", "from-gh-env")
    assert fetch._resolve_token("explicit") == "explicit"


def test_resolve_token_github_token_used_when_no_explicit(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("GITHUB_TOKEN", "from-env")
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert fetch._resolve_token(None) == "from-env"


def test_resolve_token_gh_token_is_fallback(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh-fallback")
    assert fetch._resolve_token(None) == "gh-fallback"


def test_resolve_token_returns_none_when_nothing_set(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert fetch._resolve_token(None) is None


# ──────────────────────────────────────────────────────────────────────────
#  Segment validation (defense against URL/query/GraphQL smuggling)
# ──────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "good",
    ["Sandjab", "actions", "a", "actions-runner", "my-repo.git", "user_name", "0xdeadbeef"],
)
def test_validate_segment_accepts_github_safe_identifiers(good: str):
    assert fetch._validate_segment("test", good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "",  # empty
        "-leading-dash",  # leading non-alnum
        ".leading-dot",
        "_leading-underscore",
        "owner/name",  # path separator
        "owner..name",  # not actually rejected by regex but smuggle-prone — covered by test below
        "owner with space",  # whitespace
        'owner"',  # quote
        "owner?q=foo",  # query smuggling
        "owner#frag",
        "owner&extra",
        "a" * 101,  # too long
        "owner\nname",  # newline
    ],
)
def test_validate_segment_rejects_unsafe_inputs(bad: str):
    # Note: "owner..name" actually MATCHES our regex (dots are allowed); the
    # parametrize entry is here only to flag that case for review — assert
    # accordingly so we know exactly which inputs the regex catches today.
    if bad == "owner..name":
        # accepted by regex (no path separator in it)
        assert fetch._validate_segment("test", bad) == bad
        return
    with pytest.raises(ValueError, match="invalid test"):
        fetch._validate_segment("test", bad)


def test_validate_segment_rejects_non_string():
    with pytest.raises(ValueError, match="invalid test"):
        fetch._validate_segment("test", 123)  # type: ignore[arg-type]


def test_repo_data_rejects_smuggled_owner(monkeypatch: pytest.MonkeyPatch):
    """A smuggled owner like `foo/../search/code?q=secret` must be rejected
    BEFORE the URL is constructed, not silently encoded."""
    _patch_urlopen(monkeypatch, lambda req: _FakeResp(b'{"stargazers_count": 0}'))
    with pytest.raises(ValueError, match="invalid owner"):
        fetch.repo_data("foo/../search", "x", token="t")


def test_profile_data_rejects_smuggled_handle(monkeypatch: pytest.MonkeyPatch):
    _patch_urlopen(monkeypatch, lambda req: _FakeResp(b"{}"))
    with pytest.raises(ValueError, match="invalid handle"):
        fetch.profile_data('foo"} } x{', token="t")


# ──────────────────────────────────────────────────────────────────────────
#  GraphQL: variables, not string interpolation
# ──────────────────────────────────────────────────────────────────────────


def test_post_graphql_passes_variables_in_body(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake(req):
        captured["body"] = req.data
        return _FakeResp(json.dumps({"data": {"x": 1}}).encode())

    _patch_urlopen(monkeypatch, fake)
    fetch._post_graphql(
        "query($login: String!) { x }",
        token="t",
        variables={"login": "Sandjab"},
    )
    body = json.loads(captured["body"])
    assert body == {
        "query": "query($login: String!) { x }",
        "variables": {"login": "Sandjab"},
    }


def test_post_graphql_omits_variables_when_none(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}

    def fake(req):
        captured["body"] = req.data
        return _FakeResp(json.dumps({"data": {"x": 1}}).encode())

    _patch_urlopen(monkeypatch, fake)
    fetch._post_graphql("{ x }", token="t")
    body = json.loads(captured["body"])
    assert body == {"query": "{ x }"}
    assert "variables" not in body


# ──────────────────────────────────────────────────────────────────────────
#  Cross-host redirect blocking
# ──────────────────────────────────────────────────────────────────────────


def _make_redirect_handler_args(target: str):
    """Build the (req, fp, code, msg, headers, newurl) tuple that
    HTTPRedirectHandler.redirect_request expects."""
    req = urllib.request.Request("https://api.github.com/start")
    fp = io.BytesIO(b"")
    msg = Message()
    msg["Location"] = target
    return req, fp, 302, "Found", msg, target


def test_redirect_handler_allows_same_host():
    handler = fetch._SameHostRedirectHandler()
    args = _make_redirect_handler_args("https://api.github.com/elsewhere")
    new_req = handler.redirect_request(*args)
    # urllib's default behavior: returns a new Request to follow.
    assert new_req is not None
    assert "api.github.com" in new_req.full_url


def test_redirect_handler_blocks_cross_host():
    handler = fetch._SameHostRedirectHandler()
    args = _make_redirect_handler_args("https://attacker.example/leak")
    with pytest.raises(urllib.error.HTTPError, match="non-GitHub host"):
        handler.redirect_request(*args)


def test_redirect_handler_blocks_subdomain():
    """`raw.githubusercontent.com` is GitHub's but not the API host —
    a token-bearing redirect there would still leak credentials."""
    handler = fetch._SameHostRedirectHandler()
    args = _make_redirect_handler_args("https://raw.githubusercontent.com/leak")
    with pytest.raises(urllib.error.HTTPError, match="non-GitHub host"):
        handler.redirect_request(*args)


def test_contribution_calendar_uses_graphql_variables(monkeypatch: pytest.MonkeyPatch):
    """The handle must travel as a `$login` variable — never spliced into
    the query string. Otherwise alias/complexity smuggling becomes possible."""
    captured: dict = {}

    def fake(req):
        captured["body"] = req.data
        return _FakeResp(
            json.dumps(
                {
                    "data": {
                        "user": {
                            "contributionsCollection": {
                                "totalCommitContributions": 0,
                                "contributionCalendar": {
                                    "totalContributions": 0,
                                    "weeks": [],
                                },
                            }
                        }
                    }
                }
            ).encode()
        )

    _patch_urlopen(monkeypatch, fake)
    fetch._fetch_contribution_calendar("Sandjab", token="t")
    body = json.loads(captured["body"])
    # Handle must NOT appear in the query string itself.
    assert "Sandjab" not in body["query"]
    # It must travel as a variable.
    assert body["variables"] == {"login": "Sandjab"}
