"""Theme registry for Cartouche.

Each theme is a flat dict of color tokens consumed by the SVG renderer.
The renderer never references colors directly — it only reads tokens.
Adding a new theme = adding a new dict.

Token contract (every theme must define all of these):
    bg                  page background
    grid_fine           10px grid pattern stroke
    grid_major          50px grid pattern stroke
    frame               outer border, primary structural lines
    frame_inner         inner double-border, faint structural lines
    axis                chart axes, tick marks, radar gridlines
    text_primary        title, large numbers
    text_secondary      dimensions, captions, ticks
    text_label          section labels (FIG. 01, NOTES)
    data_primary        main data line/region color
    data_fill_opacity   alpha for filled data regions (0.0-1.0)
    accent              annotation color (leader lines, callouts)

Light/dark pairs share an aesthetic family and should look like the same
drawing rendered on different paper, not like inverted colors.
"""

THEMES: dict[str, dict] = {
    # ── DRAFTING ──────────────────────────────────────────────────────────
    # Pure grayscale — achromatic technical memo. No hue at all; the data
    # series and the accent are distinguished by lightness, not by color.
    "drafting-light": {
        "bg":                "#ffffff",
        "grid_fine":         "#f0f0f0",
        "grid_major":        "#d9d9d9",
        "frame":             "#1a1a1a",
        "frame_inner":       "#999999",
        "axis":              "#999999",
        "text_primary":      "#0a0a0a",
        "text_secondary":    "#6b6b6b",
        "text_label":        "#1f1f1f",
        "data_primary":      "#2b2b2b",
        "data_fill_opacity": 0.14,
        "accent":            "#555555",
    },
    "drafting-dark": {
        "bg":                "#1a1a1a",
        "grid_fine":         "#262626",
        "grid_major":        "#333333",
        "frame":             "#f0f0f0",
        "frame_inner":       "#555555",
        "axis":              "#555555",
        "text_primary":      "#f5f5f5",
        "text_secondary":    "#999999",
        "text_label":        "#e5e5e5",
        "data_primary":      "#e0e0e0",
        "data_fill_opacity": 0.18,
        "accent":            "#a0a0a0",
    },

    # ── BLUEPRINT ─────────────────────────────────────────────────────────
    # Cyanotype lineage. Pale faded reverse, deep cyanotype original.
    "blueprint-light": {
        "bg":                "#e3edf6",
        "grid_fine":         "#d4e0ec",
        "grid_major":        "#b8cce0",
        "frame":             "#0f2540",
        "frame_inner":       "#6f8aa3",
        "axis":              "#6f8aa3",
        "text_primary":      "#082338",
        "text_secondary":    "#4f6478",
        "text_label":        "#0f2540",
        "data_primary":      "#155e75",
        "data_fill_opacity": 0.16,
        "accent":            "#b45309",
    },
    "blueprint-dark": {
        "bg":                "#0d2b45",
        "grid_fine":         "#1a3a5c",
        "grid_major":        "#245273",
        "frame":             "#cfe8ff",
        "frame_inner":       "#5b8db5",
        "axis":              "#5b8db5",
        "text_primary":      "#f0f7ff",
        "text_secondary":    "#7fa8c9",
        "text_label":        "#cfe8ff",
        "data_primary":      "#5fb3e2",
        "data_fill_opacity": 0.18,
        "accent":            "#ffb96b",
    },

    # ── VELLUM ────────────────────────────────────────────────────────────
    # Beaux-Arts engineering. Vellum cream, dark leather book.
    "vellum-light": {
        "bg":                "#f3ead4",
        "grid_fine":         "#e6dcc0",
        "grid_major":        "#d2c298",
        "frame":             "#2d1f10",
        "frame_inner":       "#8a7754",
        "axis":              "#8a7754",
        "text_primary":      "#1f150a",
        "text_secondary":    "#6b5638",
        "text_label":        "#2d1f10",
        "data_primary":      "#4a2c1f",
        "data_fill_opacity": 0.16,
        "accent":            "#8b1a1a",
    },
    "vellum-dark": {
        "bg":                "#2a1e10",
        "grid_fine":         "#382818",
        "grid_major":        "#463624",
        "frame":             "#d4a574",
        "frame_inner":       "#8a6f4a",
        "axis":              "#8a6f4a",
        "text_primary":      "#f0e3c8",
        "text_secondary":    "#b8a07a",
        "text_label":        "#d4a574",
        "data_primary":      "#e0a062",
        "data_fill_opacity": 0.20,
        "accent":            "#ef6e6e",
    },

    # ── BOTANICAL ─────────────────────────────────────────────────────────
    # 19th-century herbarium plate. Sage-and-fern ink on ivory paper,
    # deep forest at night with candle-pollen accents.
    "botanical-light": {
        "bg":                "#f3efde",
        "grid_fine":         "#e6e3cc",
        "grid_major":        "#cbd0b1",
        "frame":             "#1f3a1f",
        "frame_inner":       "#7d9474",
        "axis":              "#7d9474",
        "text_primary":      "#0f2010",
        "text_secondary":    "#5a7556",
        "text_label":        "#1f3a1f",
        "data_primary":      "#3f7a3a",
        "data_fill_opacity": 0.16,
        "accent":            "#a83a30",
    },
    "botanical-dark": {
        "bg":                "#162818",
        "grid_fine":         "#1f3522",
        "grid_major":        "#2a4530",
        "frame":             "#dfe5cc",
        "frame_inner":       "#5e6f4f",
        "axis":              "#5e6f4f",
        "text_primary":      "#eef0db",
        "text_secondary":    "#9ab088",
        "text_label":        "#dfe5cc",
        "data_primary":      "#8fc578",
        "data_fill_opacity": 0.18,
        "accent":            "#f5b94a",
    },

    # ── BLOSSOM ───────────────────────────────────────────────────────────
    # Sakura kawaii. Powder-rose ink on ivory with pearl-grey structure;
    # deep aubergine boudoir at night, with neon-soft pink data and mint
    # complement accents.
    "blossom-light": {
        "bg":                "#fff5f8",
        "grid_fine":         "#f0e3e9",
        "grid_major":        "#dfc9d4",
        "frame":             "#5b3947",
        "frame_inner":       "#b89aa6",
        "axis":              "#b89aa6",
        "text_primary":      "#2e1a26",
        "text_secondary":    "#8a7580",
        "text_label":        "#5b3947",
        "data_primary":      "#e07ab0",
        "data_fill_opacity": 0.18,
        "accent":            "#5b9fc4",
    },
    "blossom-dark": {
        "bg":                "#241624",
        "grid_fine":         "#332033",
        "grid_major":        "#432d44",
        "frame":             "#fad9e6",
        "frame_inner":       "#8d647a",
        "axis":              "#8d647a",
        "text_primary":      "#fde8ef",
        "text_secondary":    "#c69eb1",
        "text_label":        "#fad9e6",
        "data_primary":      "#ff9bcc",
        "data_fill_opacity": 0.20,
        "accent":            "#9be3d2",
    },
}

# Watermark tokens — every theme has them, defaulting to no watermark.
# Watermarked variants below override these two fields.
for _t in THEMES.values():
    _t.setdefault("watermark", None)
    _t.setdefault("watermark_opacity", 0.0)


def _with_watermark(base: dict, name: str, opacity: float = 0.10) -> dict:
    """Return a shallow copy of `base` with watermark fields set."""
    return {**base, "watermark": name, "watermark_opacity": opacity}


# ── WATERMARKED VARIANTS ──────────────────────────────────────────────────
# Same palettes as their parent families, with a bundled PNG watermark
# inlined behind the data layer at low opacity. See src/cartouche/watermarks/.
THEMES["vellum-davinci-light"]   = _with_watermark(THEMES["vellum-light"],    "davinci")
THEMES["vellum-davinci-dark"]    = _with_watermark(THEMES["vellum-dark"],     "davinci")
THEMES["botanical-floral-light"] = _with_watermark(THEMES["botanical-light"], "floral")
THEMES["botanical-floral-dark"]  = _with_watermark(THEMES["botanical-dark"],  "floral")
THEMES["blossom-kawai-light"]    = _with_watermark(THEMES["blossom-light"],   "kawai")
THEMES["blossom-kawai-dark"]     = _with_watermark(THEMES["blossom-dark"],    "kawai")


def get_theme(name: str) -> dict:
    """Return a theme dict by name. Raises KeyError with a helpful message."""
    if name not in THEMES:
        raise KeyError(
            f"Unknown theme {name!r}. Available: {', '.join(sorted(THEMES))}"
        )
    return THEMES[name]


def list_themes() -> list[str]:
    """Return all available theme names, alphabetically sorted."""
    return sorted(THEMES)
