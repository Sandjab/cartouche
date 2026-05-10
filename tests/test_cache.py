"""Tests for the disk cache used by `cartouche.fetch`.

The cache is a thin JSON-on-disk layer with TTL — these tests pin its
contract so the fetch layer can rely on it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from cartouche.cache import (
    CACHE_VERSION,
    DEFAULT_TTL_SECONDS,
    Cache,
    default_cache_dir,
)

# ──────────────────────────────────────────────────────────────────────────
#  Default location
# ──────────────────────────────────────────────────────────────────────────


def test_default_cache_dir_uses_xdg_when_set(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert default_cache_dir() == tmp_path / "cartouche"


def test_default_cache_dir_falls_back_to_home_cache(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert default_cache_dir() == tmp_path / ".cache" / "cartouche"


# ──────────────────────────────────────────────────────────────────────────
#  Basic round trip
# ──────────────────────────────────────────────────────────────────────────


def test_get_miss_returns_none(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    assert cache.get(("stargazers", "Sandjab", "cartouche")) is None


def test_put_then_get_round_trip(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    payload = ["2025-01-01", "2025-01-02", "2025-02-15"]
    cache.put(("stargazers", "Sandjab", "cartouche"), payload)
    assert cache.get(("stargazers", "Sandjab", "cartouche")) == payload


def test_put_creates_organized_subtree(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    cache.put(("languages", "Sandjab", "cartouche"), {"Python": 12345})
    assert (tmp_path / "languages" / "Sandjab" / "cartouche.json").exists()


def test_file_format_carries_version_and_timestamp(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    cache.put(("k",), {"hello": "world"})
    raw = json.loads((tmp_path / "k.json").read_text())
    assert raw["version"] == CACHE_VERSION
    assert "fetched_at" in raw
    assert "fetched_at_epoch" in raw
    assert raw["data"] == {"hello": "world"}


# ──────────────────────────────────────────────────────────────────────────
#  Disabled mode
# ──────────────────────────────────────────────────────────────────────────


def test_disabled_cache_never_writes(tmp_path: Path):
    cache = Cache(base_dir=tmp_path, enabled=False)
    cache.put(("k",), {"x": 1})
    assert not (tmp_path / "k.json").exists()


def test_disabled_cache_always_misses(tmp_path: Path):
    # Pre-populate as if we had a hot cache, then disable.
    Cache(base_dir=tmp_path).put(("k",), {"x": 1})
    assert (tmp_path / "k.json").exists()
    assert Cache(base_dir=tmp_path, enabled=False).get(("k",)) is None


# ──────────────────────────────────────────────────────────────────────────
#  TTL
# ──────────────────────────────────────────────────────────────────────────


def test_ttl_zero_treats_everything_as_stale(tmp_path: Path):
    """TTL=0 is the `--cache-ttl 0` knob: write, then immediately miss."""
    cache = Cache(base_dir=tmp_path, ttl_seconds=0)
    cache.put(("k",), {"x": 1})
    assert cache.get(("k",)) is None


def test_ttl_expired_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Older-than-TTL entries are treated as misses."""
    cache = Cache(base_dir=tmp_path, ttl_seconds=10)
    cache.put(("k",), {"x": 1})
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 1000)
    assert cache.get(("k",)) is None


def test_default_ttl_is_24h():
    assert DEFAULT_TTL_SECONDS == 24 * 60 * 60


# ──────────────────────────────────────────────────────────────────────────
#  Robustness
# ──────────────────────────────────────────────────────────────────────────


def test_corrupt_json_treated_as_miss(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    p = tmp_path / "k.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not valid json")
    assert cache.get(("k",)) is None


def test_version_mismatch_treated_as_miss(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    p = tmp_path / "k.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "version": CACHE_VERSION + 99,
                "fetched_at_epoch": time.time(),
                "data": "stale-format",
            }
        )
    )
    assert cache.get(("k",)) is None


def test_path_traversal_neutralized(tmp_path: Path):
    """A malicious key part can't escape base_dir via `..` or `/`."""
    cache = Cache(base_dir=tmp_path)
    cache.put(("../../etc", "passwd"), {"oops": True})
    # The file lands inside base_dir, not in /etc/passwd.json.
    written = list(tmp_path.rglob("*.json"))
    assert written and all(tmp_path in p.parents for p in written)


def test_atomic_write_leaves_no_tempfile(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    cache.put(("k",), {"x": 1})
    assert not list(tmp_path.rglob("*.tmp"))


# ──────────────────────────────────────────────────────────────────────────
#  Clearing
# ──────────────────────────────────────────────────────────────────────────


def test_clear_specific_key(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    cache.put(("a",), 1)
    cache.put(("b",), 2)
    assert cache.clear(("a",)) == 1
    assert cache.get(("a",)) is None
    assert cache.get(("b",)) == 2


def test_clear_all_under_base_dir(tmp_path: Path):
    cache = Cache(base_dir=tmp_path)
    cache.put(("stargazers", "X", "Y"), [])
    cache.put(("languages", "X", "Y"), {})
    cache.put(("stargazers", "X", "Z"), [])
    assert cache.clear() == 3
    assert cache.get(("stargazers", "X", "Y")) is None


def test_clear_missing_key_returns_zero(tmp_path: Path):
    assert Cache(base_dir=tmp_path).clear(("nope",)) == 0


# ──────────────────────────────────────────────────────────────────────────
#  Integration: fetch.py uses the cache
# ──────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────
#  Symlink redirect (M-3) and corrupt-payload tolerance (M-4)
# ──────────────────────────────────────────────────────────────────────────


def test_put_refuses_symlink_redirect_outside_base_dir(tmp_path: Path):
    """If a co-resident UID drops a symlink at <base_dir>/<part> pointing
    elsewhere on disk, Cache.put must refuse to follow it."""
    base = tmp_path / "cache"
    base.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # Plant the malicious symlink before any cache I/O.
    (base / "stargazers").symlink_to(elsewhere, target_is_directory=True)

    cache = Cache(base_dir=base)
    with pytest.raises(ValueError, match="outside base_dir"):
        cache.put(("stargazers", "owner", "repo"), {"x": 1})

    # And we must not have written anything inside the redirected target.
    assert not list(elsewhere.rglob("*.json"))


def test_get_refuses_symlink_redirect_outside_base_dir(tmp_path: Path):
    base = tmp_path / "cache"
    base.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    # Pre-create a "valid"-looking JSON in elsewhere.
    (elsewhere / "owner").mkdir()
    (elsewhere / "owner" / "repo.json").write_text(
        json.dumps({"version": 1, "fetched_at_epoch": time.time(), "data": "PWN"})
    )
    (base / "stargazers").symlink_to(elsewhere, target_is_directory=True)

    cache = Cache(base_dir=base)
    # Even though a syntactically-valid cache file exists at the redirected
    # path, get() must refuse to read it (returns None, treated as a miss).
    assert cache.get(("stargazers", "owner", "repo")) is None


def test_clear_does_not_unlink_outside_base_dir(tmp_path: Path):
    base = tmp_path / "cache"
    base.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    sentinel = elsewhere / "important.json"
    sentinel.write_text("{}")
    (base / "redirect").symlink_to(elsewhere, target_is_directory=True)

    Cache(base_dir=base).clear()
    assert sentinel.exists(), "clear() escaped base_dir via the symlink"


@pytest.mark.parametrize(
    "corrupt_payload",
    [
        '"not_a_dict"',
        "[1, 2, 3]",
        "null",
        "42",
        '{"version": 1, "fetched_at_epoch": "forever", "data": []}',  # str epoch
        '{"version": 1, "fetched_at_epoch": null, "data": []}',  # null epoch
        '{"version": "wrong", "fetched_at_epoch": 0, "data": []}',  # bad version
        "not even json",  # malformed
        "",  # empty file
        # JSON allows `Infinity` / `NaN` by default. Without an explicit
        # `math.isfinite` guard, `time.time() - inf < ttl` is False and
        # the entry is forever-valid (TTL bypass).
        '{"version": 1, "fetched_at_epoch": Infinity, "data": "PWN"}',
        '{"version": 1, "fetched_at_epoch": -Infinity, "data": "PWN"}',
        '{"version": 1, "fetched_at_epoch": NaN, "data": "PWN"}',
        # `bool` is a subclass of `int`. Without the explicit `isinstance(_,
        # bool)` reject, `True` would pass the type check and act as `1`.
        '{"version": 1, "fetched_at_epoch": true, "data": "PWN"}',
    ],
)
def test_get_returns_none_on_corrupt_payload(tmp_path: Path, corrupt_payload: str):
    """A forged or corrupt cache file must never crash the caller — get()
    treats it as a miss so the next fetch refreshes cleanly."""
    cache = Cache(base_dir=tmp_path)
    # Write the corrupt payload directly (bypass put()) to simulate a hostile
    # process or an interrupted previous run.
    p = cache._path(("k",))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(corrupt_payload)
    assert cache.get(("k",)) is None


def test_path_rejects_unsafe_segments_after_sanitization(tmp_path: Path):
    """If sanitization leaves something that doesn't match the safe regex
    (e.g. wildly long, non-ASCII), refuse the key rather than silently
    creating a weird-looking file."""
    cache = Cache(base_dir=tmp_path)
    # 200 chars (exceeds the 128 cap)
    with pytest.raises(ValueError, match="unsafe cache key part"):
        cache._path(("a" * 200,))
    # Empty after stripping (replace doesn't help here)
    with pytest.raises(ValueError, match="unsafe cache key part"):
        cache._path(("",))


def test_fetch_helpers_skip_network_on_cache_hit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """If the cache is hot, _cached_stargazer_dates and _cached_languages
    must not call the underlying HTTP helpers — that's the whole point."""
    from cartouche import fetch

    # Pre-fill the cache with what these helpers expect to read.
    cache = Cache(base_dir=tmp_path)
    cache.put(("stargazers", "Sandjab", "cartouche"), ["2025-01-01", "2025-02-02"])
    cache.put(("languages", "Sandjab", "cartouche"), {"Python": 1234})

    def boom(*a, **kw):
        raise AssertionError("network call made despite hot cache")

    monkeypatch.setattr(fetch, "_get_paginated", boom)
    monkeypatch.setattr(fetch, "_get_json", boom)

    dates = fetch._cached_stargazer_dates("Sandjab", "cartouche", None, cache)
    langs = fetch._cached_languages("Sandjab", "cartouche", None, cache)

    assert [d.isoformat() for d in dates] == ["2025-01-01", "2025-02-02"]
    assert langs == {"Python": 1234}
