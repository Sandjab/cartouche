"""Disk-based cache for expensive GitHub API responses.

Stargazer timelines and per-repo language byte counts are the two
endpoints that dominate `cartouche profile` runtime: the first because
it paginates over every star ever given to every public repo, the
second because it's a per-repo call multiplied by the number of repos.
Both move slowly enough that a daily refresh is more than sufficient.

This module is the lowest layer; it knows nothing about the GitHub API.
It's a JSON-on-disk key/value store with TTL.

Cache key:
    A tuple `(category: str, *parts: str)`, e.g. `("stargazers", owner, repo)`.
    Each part becomes a path segment, with `/` and `..` neutralized so
    the cache directory can never escape its root.

Cache file format:
    {
      "version": 1,
      "fetched_at": "<ISO timestamp>",
      "fetched_at_epoch": <unix seconds>,
      "data": <user payload>
    }

Disabling:
    `Cache(enabled=False)` makes every `get()` miss and every `put()`
    a no-op. Used by the `--no-cache` CLI flag.

Default location:
    `$XDG_CACHE_HOME/cartouche/` (or `~/.cache/cartouche/` if XDG isn't
    set), one JSON file per cache entry, organized into per-category
    subdirectories so a user can `rm -rf ~/.cache/cartouche/stargazers`
    to selectively invalidate.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 hours
CACHE_VERSION = 1

# After path-segment sanitization, every part of a cache key must look like
# a benign identifier. Defense-in-depth: the canonical keys today only use
# `[A-Za-z0-9._-]`, so any future caller that strays gets a clear error
# instead of a quietly mangled filename.
_PATH_PART_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def default_cache_dir() -> Path:
    """Return the platform default cache directory for Cartouche.

    Honors `XDG_CACHE_HOME` if set; otherwise falls back to `~/.cache`.
    The returned path is not created on disk — `Cache.put` does that
    lazily on first write.
    """
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "cartouche"


class Cache:
    """Filesystem-backed JSON cache with TTL.

    All four constructor knobs are independently optional:
        base_dir     — root of the cache tree. Defaults to default_cache_dir().
        ttl_seconds  — entries older than this are treated as misses.
        enabled      — set False to disable the cache entirely (no I/O).

    The cache is safe to share across concurrent processes that read
    and write to it: writes go through a tempfile + os.replace, which
    is atomic on the same filesystem.
    """

    def __init__(
        self,
        base_dir: Path | None = None,
        *,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        enabled: bool = True,
    ) -> None:
        self.base_dir = Path(base_dir) if base_dir else default_cache_dir()
        self.ttl_seconds = ttl_seconds
        self.enabled = enabled

    def _path(self, key: tuple[str, ...]) -> Path:
        """Map a key tuple to its on-disk JSON path.

        Each part is first defanged (`/` and `..` replaced with `_`) and then
        validated against `_PATH_PART_RE`. Invalid parts raise ValueError —
        we'd rather fail loudly than silently mangle a key.
        """
        if not key:
            raise ValueError("cache key must have at least one part")
        safe_parts: list[str] = []
        for p in key:
            s = str(p).replace("/", "_").replace("..", "_")
            if not _PATH_PART_RE.match(s):
                raise ValueError(
                    f"unsafe cache key part {p!r} "
                    f"(after sanitization: {s!r}); allowed: [A-Za-z0-9._-]{{1,128}}"
                )
            safe_parts.append(s)
        return self.base_dir.joinpath(*safe_parts).with_suffix(".json")

    def _ensure_under_base(self, path: Path) -> None:
        """Refuse to read/write through symlinks that escape `base_dir`.

        Without this check, a co-resident UID could drop a symlink at
        `base_dir/<part>` pointing at an arbitrary directory and silently
        redirect every cache write into it. We resolve the actual path
        each time and require it to live under the resolved `base_dir`.
        """
        base = self.base_dir.resolve()
        # path.resolve() with strict=False (the default) handles non-existing
        # tails by resolving the deepest existing ancestor.
        resolved = path.resolve()
        if not resolved.is_relative_to(base):
            raise ValueError(
                f"refusing cache I/O outside base_dir: {path} resolves to "
                f"{resolved}, which is not under {base}"
            )

    def get(self, key: tuple[str, ...]) -> Any | None:
        """Return the cached payload for `key`, or None if missing/stale.

        Treats unreadable files, type-confused payloads, and version
        mismatches as cache misses — the next `put` will overwrite, so a
        corrupt cache is self-healing rather than CLI-killing.
        """
        if not self.enabled:
            return None
        try:
            path = self._path(key)
        except ValueError:
            return None
        if not path.exists():
            return None
        try:
            self._ensure_under_base(path)
            with open(path) as f:
                payload = json.load(f)
        except Exception:
            # Any exception while reading or resolving the path counts as a
            # miss. The fetcher will then refresh from the API.
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("version") != CACHE_VERSION:
            return None
        epoch = payload.get("fetched_at_epoch")
        if not isinstance(epoch, (int, float)):
            return None
        if time.time() - epoch > self.ttl_seconds:
            return None
        return payload.get("data")

    def put(self, key: tuple[str, ...], data: Any) -> None:
        """Atomically write `data` to disk under `key`. No-op if disabled."""
        if not self.enabled:
            return
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_under_base(path)
        payload = {
            "version": CACHE_VERSION,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_at_epoch": time.time(),
            "data": data,
        }
        tmp = path.with_suffix(".json.tmp")
        try:
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2, sort_keys=True)
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def clear(self, key: tuple[str, ...] | None = None) -> int:
        """Delete one entry (if `key` is given) or every entry under base_dir.

        Returns the number of files deleted. Missing entries don't raise.
        Symlink-redirected paths are refused at the `_ensure_under_base`
        boundary — `clear()` never deletes outside `base_dir`.
        """
        if key is not None:
            try:
                path = self._path(key)
            except ValueError:
                return 0
            if path.exists():
                try:
                    self._ensure_under_base(path)
                except ValueError:
                    return 0
                path.unlink()
                return 1
            return 0
        if not self.base_dir.exists():
            return 0
        base = self.base_dir.resolve()
        n = 0
        for p in self.base_dir.rglob("*.json"):
            try:
                if not p.resolve().is_relative_to(base):
                    continue
                p.unlink()
                n += 1
            except OSError:
                pass
        return n
