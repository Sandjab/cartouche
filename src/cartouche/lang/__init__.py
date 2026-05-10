"""Language pack loader for Cartouche.

Built-in packs live as JSON next to this module:
    src/cartouche/lang/en.json
    src/cartouche/lang/fr.json
    ...

Public API:
    load(code="en", overlay_path=None) -> dict
    list_builtin() -> list[str]
    t(lang, key) -> str                # label lookup
    tmpl(lang, key, **kwargs) -> str   # template formatting
    month_short(lang, n) -> str        # 1..12 → "JAN", "FÉV", ...
    month_long(lang, n) -> str         # 1..12 → "janv.", "févr.", ...

Adding a new language: drop `<code>.json` in src/cartouche/lang/, mirroring
the schema of en.json. It will be picked up automatically by `list_builtin()`
and selectable via `--lang <code>` in the CLI.

User-defined overlays: pass `overlay_path` to `load()` (or `--lang-file PATH`
in the CLI). The overlay is deep-merged on top of the base pack — you only
need to specify keys you want to change. Example:

    {"labels": {"drawn_by": "DESSINÉ PAR"}, "templates": {"n_years": "{n} ANS"}}
"""

from __future__ import annotations

import importlib.resources as resources
import json
from datetime import date as _date
from pathlib import Path
from typing import Any

_PACKAGE_RESOURCE = "cartouche.lang"


def load(code: str = "en", overlay_path: str | Path | None = None) -> dict:
    """Load a language pack and optionally overlay user-supplied JSON.

    Raises KeyError for unknown built-in codes, FileNotFoundError if
    overlay_path doesn't exist.
    """
    base = _load_builtin(code)
    if overlay_path is not None:
        overlay = json.loads(Path(overlay_path).read_text(encoding="utf-8"))
        base = _deep_merge(base, overlay)
    return base


def list_builtin() -> list[str]:
    """Return all built-in language codes, sorted alphabetically."""
    out: list[str] = []
    for entry in resources.files(_PACKAGE_RESOURCE).iterdir():
        name = entry.name
        if name.endswith(".json"):
            out.append(name[:-5])
    return sorted(out)


def t(lang: dict, key: str) -> str:
    """Look up a static label. Raises KeyError on missing key."""
    try:
        return lang["labels"][key]
    except KeyError:
        raise KeyError(
            f"Lang pack {lang.get('code', '?')!r} missing labels.{key!r}"
        ) from None


def tmpl(lang: dict, key: str, **kwargs: Any) -> str:
    """Format a template string with kwargs."""
    try:
        template = lang["templates"][key]
    except KeyError:
        raise KeyError(
            f"Lang pack {lang.get('code', '?')!r} missing templates.{key!r}"
        ) from None
    return template.format(**kwargs)


def month_short(lang: dict, month_1_to_12: int) -> str:
    """Return the short uppercase month name (e.g. 'JAN', 'FÉV')."""
    return lang["months_short"][month_1_to_12 - 1]


def month_long(lang: dict, month_1_to_12: int) -> str:
    """Return the long lowercase month name (e.g. 'janv.', 'Jan')."""
    return lang["months_long"][month_1_to_12 - 1]


def format_date_long(lang: dict, d: _date) -> str:
    """Format a date as '{long_month} {year}', e.g. 'sept. 2025' or 'Sep 2025'."""
    return f"{month_long(lang, d.month)} {d.year}"


# ──────────────────────────────────────────────────────────────────────────
#  Internal helpers
# ──────────────────────────────────────────────────────────────────────────

def _load_builtin(code: str) -> dict:
    candidate = resources.files(_PACKAGE_RESOURCE).joinpath(f"{code}.json")
    if not candidate.is_file():
        raise KeyError(
            f"Unknown language code {code!r}. Built-in packs: {', '.join(list_builtin())}"
        )
    return json.loads(candidate.read_text(encoding="utf-8"))


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge `overlay` into a copy of `base`. Lists and scalars
    are replaced wholesale; dicts are merged key-by-key."""
    result = dict(base)
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result
