"""Watermark loader for bundled PNG watermarks.

Mirrors the `lang/` subpackage architecture: bundled PNG files are looked
up via importlib.resources, base64-encoded, and inlined into the SVG
output through an `<image href="data:image/png;base64,..."/>` primitive
— so no external fetch is needed at view time and the SVG stays
self-contained (Cartouche's invariant).

Adding a watermark = drop a `<name>.png` next to this file. The wheel
must ship it (see pyproject.toml `[tool.hatch.build.targets.wheel.force-include]`).
"""

from __future__ import annotations

import base64
from importlib.resources import files


def list_builtin() -> list[str]:
    """Return the names (without extension) of all bundled watermarks,
    alphabetically sorted."""
    pkg = files(__name__)
    return sorted(
        p.name.removesuffix(".png")
        for p in pkg.iterdir()
        if p.is_file() and p.name.endswith(".png")
    )


def load(name: str) -> bytes:
    """Return the raw PNG bytes for the watermark `name` (no extension).
    Raises KeyError with the available list if not found."""
    pkg = files(__name__)
    path = pkg / f"{name}.png"
    if not path.is_file():
        raise KeyError(
            f"Unknown watermark {name!r}. "
            f"Available: {', '.join(list_builtin())}"
        )
    return path.read_bytes()


def as_data_uri(name: str) -> str:
    """Return a `data:image/png;base64,...` URI for the watermark,
    ready to drop into an `<image href=...>` element."""
    b64 = base64.b64encode(load(name)).decode("ascii")
    return f"data:image/png;base64,{b64}"
