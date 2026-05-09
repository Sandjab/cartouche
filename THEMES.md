# Cartouche Theme Catalogue

Six themes in three aesthetic families, each with a light and a dark
counterpart. Every preview below is rendered from the **same mock fixture**
(`mock_repo()` — 23 stars, 67 commits over 30 days, two annotations) so the
only thing changing between two cells is the palette and the typographic
hierarchy. Pick a theme via `--theme <name>` on the CLI or
`get_theme(<name>)` in the Python API.

```bash
cartouche themes  # list all six
cartouche repo Sandjab/Athanor --mock --theme vellum-dark --out /tmp/d.svg
```

| Family       | Light                 | Dark                |
|--------------|-----------------------|---------------------|
| **Drafting** | `drafting-light`      | `drafting-dark`     |
| **Blueprint**| `blueprint-light`     | `blueprint-dark`    |
| **Vellum**   | `vellum-light`        | `vellum-dark`       |

---

## Drafting

White paper, indigo ink. **Achromatic, neutral, the tone of a technical
memo** — it disappears into a documentation page rather than calling
attention to itself. The dark variant flips to charcoal paper without
shifting the underlying hue family. Pick this when the dashboard sits next
to body copy and shouldn't fight for attention.

| `drafting-light` | `drafting-dark` |
|---|---|
| <img src="examples/outputs/repo-drafting-light.svg" alt="drafting-light theme preview" width="100%"/> | <img src="examples/outputs/repo-drafting-dark.svg" alt="drafting-dark theme preview" width="100%"/> |

---

## Blueprint

Cyanotype lineage. The **pale faded reverse** of an architectural blueprint
on the light side, and a **deep nighttime Prussian blue dive** on the dark
side — the most "engineering-drawing"-coded of the three families, and the
default theme for the CLI. Reach for this when you want the dashboard to
read instantly as a technical artefact.

| `blueprint-light` | `blueprint-dark` |
|---|---|
| <img src="examples/outputs/repo-blueprint-light.svg" alt="blueprint-light theme preview" width="100%"/> | <img src="examples/outputs/repo-blueprint-dark.svg" alt="blueprint-dark theme preview" width="100%"/> |

---

## Vellum

Cream parchment with sepia ink on the light side; aged leather and gold leaf
on the dark side. **A Beaux-Arts feel rather than engineering** — closer to
a 19th-century naturalist plate than to a Bauhaus blueprint. Use this when
the surrounding context is editorial, hand-crafted, or deliberately
nostalgic; it makes the data feel curated rather than instrumented.

| `vellum-light` | `vellum-dark` |
|---|---|
| <img src="examples/outputs/repo-vellum-light.svg" alt="vellum-light theme preview" width="100%"/> | <img src="examples/outputs/repo-vellum-dark.svg" alt="vellum-dark theme preview" width="100%"/> |

---

## Adding a theme

A theme is a flat dict of 12 color tokens — see `src/cartouche/themes.py`
for the contract. Adding one is ~12 lines: copy an existing entry, change
the palette, and the rest of the code (renderer, CLI, tests) picks it up
automatically. To regenerate this catalogue's previews:

```bash
PYTHONPATH=src python3 -m cartouche repo Sandjab/Athanor --mock \
  --theme <new-theme-light> --out examples/outputs/repo-<new-theme-light>.svg
PYTHONPATH=src python3 -m cartouche repo Sandjab/Athanor --mock \
  --theme <new-theme-dark>  --out examples/outputs/repo-<new-theme-dark>.svg
```

Then add a section above following the same structure (paragraph + 2-column
table linking to the two SVGs).
