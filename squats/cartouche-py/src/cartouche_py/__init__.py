"""Placeholder package — the real project is `cartouche-svg`.

This module exists only to reserve the `cartouche-py` slot on PyPI so that
no third party can later publish a hostile package under that typo-prone
name. Importing it raises immediately.
"""

raise ImportError(
    "`cartouche-py` is a placeholder package. "
    "The real project is `cartouche-svg`. "
    "Please install the correct package: pip install cartouche-svg"
)
