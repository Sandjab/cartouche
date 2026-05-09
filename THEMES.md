# Cartouche Theme Catalogue

Six themes in three aesthetic families, each with a light and a dark
counterpart. Every preview below is rendered from the **same mock fixtures**
(`mock_repo()` and `mock_profile()`) so the only thing changing between two
cells is the palette and the typographic hierarchy. Pick a theme via
`--theme <name>` on the CLI or `get_theme(<name>)` in the Python API.

```bash
cartouche themes  # list all six
cartouche repo    Sandjab/Athanor --mock --theme vellum-dark    --out /tmp/r.svg
cartouche profile Sandjab          --mock --theme blueprint-dark --out /tmp/p.svg
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

### Repo dashboard

| `drafting-light` | `drafting-dark` |
|---|---|
| <img src="examples/outputs/repo-drafting-light.svg" alt="repo · drafting-light" width="100%"/> | <img src="examples/outputs/repo-drafting-dark.svg" alt="repo · drafting-dark" width="100%"/> |

### Profile dashboard

| `drafting-light` | `drafting-dark` |
|---|---|
| <img src="examples/outputs/profile-drafting-light.svg" alt="profile · drafting-light" width="100%"/> | <img src="examples/outputs/profile-drafting-dark.svg" alt="profile · drafting-dark" width="100%"/> |

---

## Blueprint

Cyanotype lineage. The **pale faded reverse** of an architectural blueprint
on the light side, and a **deep nighttime Prussian blue dive** on the dark
side — the most "engineering-drawing"-coded of the three families, and the
default theme for the CLI. Reach for this when you want the dashboard to
read instantly as a technical artefact.

### Repo dashboard

| `blueprint-light` | `blueprint-dark` |
|---|---|
| <img src="examples/outputs/repo-blueprint-light.svg" alt="repo · blueprint-light" width="100%"/> | <img src="examples/outputs/repo-blueprint-dark.svg" alt="repo · blueprint-dark" width="100%"/> |

### Profile dashboard

| `blueprint-light` | `blueprint-dark` |
|---|---|
| <img src="examples/outputs/profile-blueprint-light.svg" alt="profile · blueprint-light" width="100%"/> | <img src="examples/outputs/profile-blueprint-dark.svg" alt="profile · blueprint-dark" width="100%"/> |

---

## Vellum

Cream parchment with sepia ink on the light side; aged leather and gold leaf
on the dark side. **A Beaux-Arts feel rather than engineering** — closer to
a 19th-century naturalist plate than to a Bauhaus blueprint. Use this when
the surrounding context is editorial, hand-crafted, or deliberately
nostalgic; it makes the data feel curated rather than instrumented.

### Repo dashboard

| `vellum-light` | `vellum-dark` |
|---|---|
| <img src="examples/outputs/repo-vellum-light.svg" alt="repo · vellum-light" width="100%"/> | <img src="examples/outputs/repo-vellum-dark.svg" alt="repo · vellum-dark" width="100%"/> |

### Profile dashboard

| `vellum-light` | `vellum-dark` |
|---|---|
| <img src="examples/outputs/profile-vellum-light.svg" alt="profile · vellum-light" width="100%"/> | <img src="examples/outputs/profile-vellum-dark.svg" alt="profile · vellum-dark" width="100%"/> |

---

## Adding a theme

A theme is a flat dict of 12 color tokens — see `src/cartouche/themes.py`
for the contract. Adding one is ~12 lines: copy an existing entry, change
the palette, and the rest of the code (renderer, CLI, tests) picks it up
automatically. To regenerate this catalogue's previews for a new theme:

```bash
for kind in repo profile; do
  for variant in light dark; do
    PYTHONPATH=src python3 -m cartouche $kind \
      $([ "$kind" = repo ] && echo "Sandjab/Athanor" || echo "Sandjab") \
      --mock --theme NEW-THEME-$variant \
      --out examples/outputs/$kind-NEW-THEME-$variant.svg
  done
done
```

Then add a section above following the same structure (paragraph + two
2-column tables, one per dashboard kind).
