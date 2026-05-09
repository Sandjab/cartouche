"""Cartouche — blueprint-style dashboards for GitHub repos and profiles.

Two dashboards: `cartouche.render.repo` and `cartouche.render.profile`.
Six themes: see `cartouche.themes`.
Languages: see `cartouche.lang` (en + fr built-in, custom packs welcomed).
Generated SVGs go in your README via the <picture> tag for light/dark.
"""

from . import lang
from .themes import THEMES, get_theme, list_themes

__version__ = "0.2.0"
__all__ = ["THEMES", "get_theme", "list_themes", "lang", "__version__"]
