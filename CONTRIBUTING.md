# Contributing to Cartouche

Thanks for considering a contribution. This page covers the
practical bits — for the architectural rationale and the invariants
to keep sacred, see [`CLAUDE.md`](CLAUDE.md).

## Getting set up

```bash
git clone https://github.com/Sandjab/cartouche
cd cartouche
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Sanity checklist before opening a PR

```bash
ruff check .                   # lint
ruff format --check .          # format (run `ruff format .` to fix)
pytest                         # 147 tests, ~0.3s
python -m cartouche repo Sandjab/cartouche --mock --out /tmp/d.svg  # smoke
```

The CI runs the same four commands across Python 3.10 – 3.13 plus a
wheel + sdist build, so there's no surprise after push.

## What to know before changing things

- **Tokens, not colors** in renderers. Adding a hex literal in
  `render/*.py` will fail review. Add a token to *every* theme in
  `themes.py` instead.
- **Lang pack literals, not English/French strings** in renderers.
  Every label flows through `t(lang, key)` or `tmpl(lang, key, **kw)`,
  and every new key needs an entry in **both** `lang/en.json` and
  `lang/fr.json` (the test `test_lang_has_all_required_keys` enforces
  this).
- **The data dict is a contract.** `mock.py` and `fetch.py` produce
  the same shape that `render.repo.render` and `render.profile.render`
  consume. Changing one side requires changing all three.
- **No JS, no `<foreignObject>`, no web fonts.** GitHub's SVG renderer
  strips all of these.
- **Stdlib only at runtime.** `pyproject.toml` declares
  `dependencies = []` — keep it that way.

`CLAUDE.md` has the full version of these rules, plus per-file
"things to know" notes.

## Commit style

Conventional commits, short imperative subject under 70 chars:

```
feat(themes): add a new dark variant for the vellum family
fix(fetch): handle 403 rate-limit response
docs: tighten the auto-update workflow example
test: cover the cache TTL boundary
```

A body is appreciated when the *why* isn't obvious from the diff.

## Adding things

| You want to add… | Steps |
|---|---|
| A theme | New entry in `THEMES` (12 tokens) → `pytest` → optionally regenerate samples in `examples/outputs/` |
| A language pack | Drop `lang/<code>.json` → add to `[tool.hatch.build.targets.wheel.force-include]` → `pytest` |
| A label/template key | Add to `en.json` *and* `fr.json` → list it in `REQUIRED_LANG_LABELS` / `REQUIRED_LANG_TEMPLATES` in tests → use it via `t()` / `tmpl()` |
| A new figure on the dashboard | New private `_fig_*` in `render/repo.py` or `render/profile.py` → pick non-overlapping y-band → extend the `RepoData` / `ProfileData` TypedDict + the `mock.py` and `fetch.py` producers |

## Reporting

Bug? Feature idea? Open an issue at
<https://github.com/Sandjab/cartouche/issues>. A minimal repro
(`cartouche repo OWNER/REPO --mock --theme … --out /tmp/d.svg` plus
the resulting SVG, or a stack trace) goes a very long way.

## License

By contributing you agree that your changes ship under the project's
[MIT license](LICENSE).
