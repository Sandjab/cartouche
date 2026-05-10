"""Placeholder package — the real project is `cartouche-svg`.

This module exists only to reserve the `cartouchesvg` slot on PyPI so that
no third party can later publish a hostile package under that typo-prone
name. Importing it raises immediately.
"""

raise ImportError(
    "`cartouchesvg` is a placeholder package. "
    "The real project is `cartouche-svg` (with a hyphen). "
    "Please install the correct package: pip install cartouche-svg"
)
