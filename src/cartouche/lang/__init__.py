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
import string
from datetime import date as _date
from pathlib import Path
from typing import Any

_PACKAGE_RESOURCE = "cartouche.lang"


class _SafeFormatter(string.Formatter):
    """A `str.Formatter` that rejects every form of templating power that
    would let a user-supplied `--lang-file` overlay escape its sandbox:

    - **Attribute access** in `field_name` (`{date.__class__}`) — would walk
      the kwargs object graph for information disclosure.
    - **Item access** in `field_name` (`{n[0]}`) — same problem.
    - **Conversions** (`{n!r}`, `{n!s}`, `{n!a}`) — invoke `__repr__`/`__str__`
      on the value, which leaks class info on rich objects and produces
      surprising quoting on strings.
    - **Format specs** (`{n:>50000000}`, `{n:.2f}`, …) — the width field is
      a trivial DoS (CPython materializes the full padded string), and
      nested specs (`{n:{w}}`) reintroduce the placeholder problem one
      level deeper.

    Plain `{name}` placeholders against bare kwargs are the only thing
    allowed. Today every built-in template fits this rule (verified by the
    test suite); if a future template legitimately needs a format spec,
    the policy below should be relaxed *and* extended with explicit
    bounds-checking, not silently widened.
    """

    def get_field(self, field_name: str, args: tuple, kwargs: dict) -> tuple:
        if "." in field_name or "[" in field_name:
            raise ValueError(
                f"unsafe placeholder {field_name!r} in template "
                f"(attribute and item access are not allowed)"
            )
        return super().get_field(field_name, args, kwargs)

    def parse(self, format_string):
        for literal_text, field_name, format_spec, conversion in super().parse(format_string):
            if conversion is not None:
                raise ValueError(
                    f"unsafe conversion !{conversion} in template "
                    f"(only plain {{name}} placeholders are allowed)"
                )
            if format_spec:
                raise ValueError(
                    f"unsafe format spec {format_spec!r} in template "
                    f"(only plain {{name}} placeholders are allowed)"
                )
            yield literal_text, field_name, format_spec, conversion


_SAFE_FORMATTER = _SafeFormatter()


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
        raise KeyError(f"Lang pack {lang.get('code', '?')!r} missing labels.{key!r}") from None


def tmpl(lang: dict, key: str, **kwargs: Any) -> str:
    """Format a template string with kwargs.

    Templates are resolved through `_SafeFormatter`, which forbids `.` and `[`
    in field names so a malicious `--lang-file` overlay cannot introspect the
    kwargs object graph (e.g. `{date.__class__}`).
    """
    try:
        template = lang["templates"][key]
    except KeyError:
        raise KeyError(f"Lang pack {lang.get('code', '?')!r} missing templates.{key!r}") from None
    return _SAFE_FORMATTER.vformat(template, (), kwargs)


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
