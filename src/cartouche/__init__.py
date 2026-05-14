"""Cartouche — technical-drawing dashboards for GitHub repos and profiles.

Two dashboards: `cartouche.render.repo` and `cartouche.render.profile`.
Sixteen themes (incl. watermarked variants): see `cartouche.themes`.
Languages: see `cartouche.lang` (en + fr built-in, custom packs welcomed).
Generated SVGs go in your README via the <picture> tag for light/dark.
"""

__version__ = "0.2.2"

# Import order matters: __version__ is defined first so submodules that
# read it (e.g. fetch.USER_AGENT) work when loaded later, and the data-
# shape TypedDicts are imported last so they pick up everything they
# transitively depend on.
from . import lang  # noqa: E402
from .cache import Cache  # noqa: E402
from .render.profile import ProfileData  # noqa: E402
from .render.repo import RepoData  # noqa: E402
from .themes import THEMES, get_theme, list_themes  # noqa: E402

__all__ = [
    "THEMES",
    "Cache",
    "ProfileData",
    "RepoData",
    "__version__",
    "get_theme",
    "lang",
    "list_themes",
]
