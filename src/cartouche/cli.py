"""Command-line entry point for Cartouche.

Usage:
    cartouche repo OWNER/REPO  [--theme THEME] [--lang CODE] [--lang-file PATH]
                               [--out PATH] [--token TOKEN] [--mock]
    cartouche profile USER     [--theme THEME] [--lang CODE] [--lang-file PATH]
                               [--out PATH] [--token TOKEN] [--mock]
    cartouche themes           # list available themes
    cartouche langs            # list available language packs
    cartouche --version

Examples:
    cartouche repo Sandjab/Athanor --theme blueprint-light --out dashboard.svg
    cartouche profile Sandjab --theme drafting-dark --lang fr
    cartouche repo myorg/myrepo --mock --lang fr --lang-file ./my-overrides.json
    cartouche themes
    cartouche langs

Token resolution:    --token > $GITHUB_TOKEN > $GH_TOKEN > anonymous (rate-limited).
Language defaults to English. Override with `--lang fr` (built-in), or supply
your own JSON overlay via `--lang-file path/to/custom.json` to tweak any keys.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, lang as lang_module
from .themes import get_theme, list_themes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cartouche",
        description="Blueprint-style dashboards for GitHub repos and profiles.",
    )
    parser.add_argument("--version", action="version",
                        version=f"cartouche {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # repo
    p_repo = sub.add_parser("repo", help="Render a repository dashboard")
    p_repo.add_argument("target", metavar="OWNER/REPO",
                        help="GitHub repository, e.g. Sandjab/Athanor")
    _add_common_args(p_repo)

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
    p.add_argument("--theme", default="blueprint-light",
                   choices=list_themes(),
                   help="Theme name (default: blueprint-light)")
    p.add_argument("--lang", default="en",
                   help="Language pack code (default: en). "
                        "Use `cartouche langs` to list built-in packs.")
    p.add_argument("--lang-file", default=None, dest="lang_file",
                   help="Path to a JSON file that overlays the base lang pack. "
                        "Only specify keys you want to override.")
    p.add_argument("--out", default="-",
                   help="Output file path (default: stdout)")
    p.add_argument("--token", default=None,
                   help="GitHub token; falls back to $GITHUB_TOKEN / $GH_TOKEN")
    p.add_argument("--mock", action="store_true",
                   help="Use canned data (no API call) — for testing layouts")


def _load_lang(args: argparse.Namespace) -> dict:
    try:
        return lang_module.load(args.lang, overlay_path=args.lang_file)
    except KeyError as e:
        sys.stderr.write(f"error: {e}\n")
        raise SystemExit(2)
    except FileNotFoundError as e:
        sys.stderr.write(f"error: lang file not found: {e}\n")
        raise SystemExit(2)


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
            data = fetch.repo_data(owner, name, token=args.token, lang=lang)
        except Exception as e:
            sys.stderr.write(f"error: {e}\n")
            return 3

    from .render import repo as repo_render
    svg = repo_render.render(data, get_theme(args.theme), lang=lang)
    return _write(svg, args.out)


def _render_profile(args: argparse.Namespace) -> int:
    lang = _load_lang(args)

    if args.mock:
        from .mock import mock_profile
        data = mock_profile(args.target, lang=lang)
    else:
        from . import fetch
        try:
            data = fetch.profile_data(args.target, token=args.token, lang=lang)
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
