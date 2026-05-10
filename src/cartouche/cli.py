"""Command-line entry point for Cartouche.

Usage:
    cartouche repo OWNER/REPO  [--theme THEME] [--lang CODE] [--lang-file PATH]
                               [--annotations-file PATH]
                               [--out PATH] [--token TOKEN] [--mock]
                               [--no-cache] [--cache-ttl SECONDS] [--cache-dir PATH]
    cartouche profile USER     [--theme THEME] [--lang CODE] [--lang-file PATH]
                               [--out PATH] [--token TOKEN] [--mock]
                               [--no-cache] [--cache-ttl SECONDS] [--cache-dir PATH]
    cartouche themes           # list available themes
    cartouche langs            # list available language packs
    cartouche --version

Examples:
    cartouche repo Sandjab/Athanor --theme blueprint-light --out dashboard.svg
    cartouche profile Sandjab --theme drafting-dark --lang fr
    cartouche repo myorg/myrepo --mock --lang fr --lang-file ./my-overrides.json
    cartouche repo myorg/myrepo --annotations-file my-events.json
    cartouche profile Sandjab --no-cache       # force fresh API fetch
    cartouche themes
    cartouche langs

Token resolution:    --token > $GITHUB_TOKEN > $GH_TOKEN > anonymous (rate-limited).
Language defaults to English. Override with `--lang fr` (built-in), or supply
your own JSON overlay via `--lang-file path/to/custom.json` to tweak any keys.
Custom callouts on the star-history line are added via `--annotations-file
path/to/events.json` (repo dashboard only); see `_load_annotations_overlay`
docstring for the schema.

Caching: stargazer timelines and per-repo language counts are cached on
disk under `$XDG_CACHE_HOME/cartouche/` (default 24h TTL). The cache
makes a follow-up profile render of the same handle near-instant. Use
`--no-cache` to skip it, `--cache-ttl 0` to force a refresh once, or
`--cache-dir PATH` to relocate.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from . import lang as lang_module
from .cache import Cache, default_cache_dir
from .themes import get_theme, list_themes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cartouche",
        description="Technical-drawing dashboards for GitHub repos and profiles.",
    )
    parser.add_argument("--version", action="version", version=f"cartouche {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # repo
    p_repo = sub.add_parser("repo", help="Render a repository dashboard")
    p_repo.add_argument(
        "target", metavar="OWNER/REPO", help="GitHub repository, e.g. Sandjab/Athanor"
    )
    _add_common_args(p_repo)
    p_repo.add_argument(
        "--annotations-file",
        default=None,
        dest="annotations_file",
        help="Path to a JSON file with custom annotations on "
        "the star-history line. Replaces the auto-detected "
        "first-star + biggest-spike callouts.",
    )

    # profile
    p_prof = sub.add_parser("profile", help="Render a user profile dashboard")
    p_prof.add_argument("target", metavar="USER", help="GitHub handle")
    _add_common_args(p_prof)

    # listings
    sub.add_parser("themes", help="List available theme names")
    sub.add_parser("langs", help="List available language packs")

    args = parser.parse_args(argv)

    if args.command == "themes":
        print("\n".join(list_themes()))
        return 0
    if args.command == "langs":
        print("\n".join(lang_module.list_builtin()))
        return 0
    if args.command == "repo":
        return _render_repo(args)
    if args.command == "profile":
        return _render_profile(args)
    return 1


def _add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--theme",
        default="blueprint-light",
        choices=list_themes(),
        help="Theme name (default: blueprint-light)",
    )
    p.add_argument(
        "--lang",
        default="en",
        help="Language pack code (default: en). Use `cartouche langs` to list built-in packs.",
    )
    p.add_argument(
        "--lang-file",
        default=None,
        dest="lang_file",
        help="Path to a JSON file that overlays the base lang pack. "
        "Only specify keys you want to override.",
    )
    p.add_argument("--out", default="-", help="Output file path (default: stdout)")
    p.add_argument(
        "--token", default=None, help="GitHub token; falls back to $GITHUB_TOKEN / $GH_TOKEN"
    )
    p.add_argument(
        "--mock", action="store_true", help="Use canned data (no API call) — for testing layouts"
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        dest="no_cache",
        help="Disable the on-disk cache (force fresh API fetches)",
    )
    p.add_argument(
        "--cache-ttl",
        type=int,
        default=None,
        dest="cache_ttl",
        help="Cache TTL in seconds (default 86400 = 24h). Set to 0 to force a one-shot refresh.",
    )
    p.add_argument(
        "--cache-dir",
        default=None,
        dest="cache_dir",
        help=f"Cache directory (default: {default_cache_dir()})",
    )


def _load_lang(args: argparse.Namespace) -> dict:
    try:
        return lang_module.load(args.lang, overlay_path=args.lang_file)
    except KeyError as e:
        sys.stderr.write(f"error: {e}\n")
        raise SystemExit(2) from None
    except FileNotFoundError as e:
        sys.stderr.write(f"error: lang file not found: {e}\n")
        raise SystemExit(2) from None


def _build_cache(args: argparse.Namespace) -> Cache:
    """Construct a Cache from the CLI flags, with sensible defaults."""
    base_dir = Path(args.cache_dir) if args.cache_dir else None
    kwargs: dict = {"enabled": not args.no_cache}
    if args.cache_ttl is not None:
        kwargs["ttl_seconds"] = max(0, args.cache_ttl)
    return Cache(base_dir=base_dir, **kwargs)


def _render_repo(args: argparse.Namespace) -> int:
    if "/" not in args.target:
        sys.stderr.write(f"error: expected OWNER/REPO, got '{args.target}'\n")
        return 2
    owner, name = args.target.split("/", 1)
    lang = _load_lang(args)

    if args.mock:
        from .mock import mock_repo

        data = mock_repo(owner, name, lang=lang)
    else:
        from . import fetch

        try:
            data = fetch.repo_data(
                owner, name, token=args.token, lang=lang, cache=_build_cache(args)
            )
        except Exception as e:
            sys.stderr.write(f"error: {e}\n")
            return 3

    if args.annotations_file:
        data["annotations"] = _load_annotations_overlay(args.annotations_file, data["star_history"])

    from .render import repo as repo_render

    svg = repo_render.render(data, get_theme(args.theme), lang=lang)
    return _write(svg, args.out)


def _load_annotations_overlay(path: str, star_history: list[dict]) -> list[dict]:
    """Read a custom-annotations JSON overlay and normalise it to the contract
    consumed by `render.repo` (`Annotation` TypedDict).

    File format: a JSON array of objects, each with:
        date         (str, ISO YYYY-MM-DD)        required
        label_top    (str)                        required
        label_bottom (str)                        required
        count        (int)                        optional — derived from
                                                  star_history if absent
                                                  (latest entry ≤ date)

    Errors exit the CLI with code 2 (bad input) and a one-line stderr message.
    """
    try:
        with open(path, encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        sys.stderr.write(f"error: annotations file not found: {path}\n")
        raise SystemExit(2) from None
    except json.JSONDecodeError as e:
        sys.stderr.write(f"error: annotations file is not valid JSON: {e}\n")
        raise SystemExit(2) from None

    if not isinstance(items, list):
        sys.stderr.write("error: annotations file must contain a JSON list at the top level.\n")
        raise SystemExit(2)

    result: list[dict] = []
    for i, entry in enumerate(items):
        if not isinstance(entry, dict):
            sys.stderr.write(f"error: annotation #{i}: must be a JSON object.\n")
            raise SystemExit(2)
        for required in ("date", "label_top", "label_bottom"):
            if required not in entry:
                sys.stderr.write(f"error: annotation #{i}: missing required key {required!r}.\n")
                raise SystemExit(2)
        # Strict shape validation: every field is type-checked here so that
        # the renderer never sees a string-where-an-int-was-expected from a
        # hostile or sloppy JSON file.
        date_raw = entry["date"]
        if not isinstance(date_raw, str):
            sys.stderr.write(f"error: annotation #{i}: 'date' must be a string.\n")
            raise SystemExit(2)
        try:
            datetime.strptime(date_raw, "%Y-%m-%d")
        except ValueError:
            sys.stderr.write(
                f"error: annotation #{i}: 'date' must be ISO 'YYYY-MM-DD', got {date_raw!r}.\n"
            )
            raise SystemExit(2) from None
        for label_key in ("label_top", "label_bottom"):
            if not isinstance(entry[label_key], str):
                sys.stderr.write(f"error: annotation #{i}: {label_key!r} must be a string.\n")
                raise SystemExit(2)
        count_raw = entry.get("count")
        if count_raw is None:
            count = _interpolate_count(date_raw, star_history)
        else:
            if not isinstance(count_raw, int) or isinstance(count_raw, bool):
                sys.stderr.write(
                    f"error: annotation #{i}: 'count' must be an integer if provided, "
                    f"got {type(count_raw).__name__}.\n"
                )
                raise SystemExit(2)
            count = count_raw
        result.append(
            {
                "date": date_raw,
                "count": count,
                "label_top": entry["label_top"],
                "label_bottom": entry["label_bottom"],
            }
        )
    return result


def _interpolate_count(target_date: str, history: list[dict]) -> int:
    """Return the cumulative star count at `target_date` by finding the latest
    history entry on or before that date. ISO date strings sort lexically, so
    no datetime parsing is needed."""
    best = 0
    for h in history:
        if h["date"] <= target_date:
            best = h["count"]
        else:
            break
    return best


def _render_profile(args: argparse.Namespace) -> int:
    lang = _load_lang(args)

    if args.mock:
        from .mock import mock_profile

        data = mock_profile(args.target, lang=lang)
    else:
        from . import fetch

        try:
            data = fetch.profile_data(
                args.target, token=args.token, lang=lang, cache=_build_cache(args)
            )
        except Exception as e:
            sys.stderr.write(f"error: {e}\n")
            return 3

    from .render import profile as profile_render

    svg = profile_render.render(data, get_theme(args.theme), lang=lang)
    return _write(svg, args.out)


def _write(svg: str, out: str) -> int:
    if out == "-":
        sys.stdout.write(svg)
    else:
        with open(out, "w", encoding="utf-8") as f:
            f.write(svg)
        sys.stderr.write(f"wrote {out} ({len(svg):,} bytes)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
