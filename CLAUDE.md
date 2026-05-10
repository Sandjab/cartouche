# CLAUDE.md

> Handoff document for Claude Code CLI.
> If you're a human reading this, [README.md](README.md) is more useful.

## Project overview

**Cartouche** is a zero-runtime-dependency Python library that generates
technical-drawing SVG dashboards for GitHub repositories and profiles. It
ships as `cartouche-svg` on PyPI and exposes a `cartouche` CLI plus a
clean Python API.

The output SVGs are pure primitives (no JS, no foreignObject, no web
fonts) so they render identically in GitHub READMEs, MDN docs, and any
SVG viewer. They get committed via GitHub Actions and embedded in READMEs
through the `<picture>` tag for light/dark modes.

Current version: **0.2.0** (i18n landed). The codebase is small and
intentionally legible — read it end-to-end if needed; it's ~900 LOC.

## Repository layout

```
cartouche/
├── pyproject.toml             # hatchling, zero deps, packages JSON files
├── README.md                  # user-facing docs (English, default)
├── README-fr.md               # user-facing docs (French)
├── CLAUDE.md                  # ← you are here
├── LICENSE                    # MIT
├── src/cartouche/
│   ├── __init__.py            # re-exports themes + lang
│   ├── __main__.py            # python -m cartouche
│   ├── cli.py                 # argparse entry point
│   ├── themes.py              # 16-theme registry (dict-of-dicts)
│   ├── fetch.py               # GitHub REST + GraphQL, stdlib urllib only
│   ├── cache.py               # disk cache (TTL JSON) for hot fetch paths
│   ├── mock.py                # canned data fixtures (no API)
│   ├── lang/
│   │   ├── __init__.py        # load(), list_builtin(), t(), tmpl(), helpers
│   │   ├── en.json            # default language pack
│   │   └── fr.json            # French language pack
│   └── render/
│       ├── __init__.py
│       ├── primitives.py      # SVG building blocks (frame, grid, radar, …)
│       ├── repo.py            # repo dashboard composer
│       └── profile.py         # profile dashboard composer
├── examples/
│   ├── workflows/
│   │   ├── repo-dashboard.yml      # GH Actions workflow for repos
│   │   └── profile-dashboard.yml   # GH Actions workflow for profiles
│   └── outputs/               # 34 sample SVGs (16 themes × 2 dashboards + 2 FR demos)
└── tests/
    ├── test_render.py         # parametrized renderer tests
    ├── test_cache.py          # disk cache contract
    └── test_fetch.py          # HTTP layer (urlopen monkey-patched)
```

## Commands

```bash
# Install for development (editable, with dev extras)
pip install -e ".[dev]"

# Run the test suite (preferred)
pytest

# Or via PYTHONPATH if not installed
PYTHONPATH=src python -m pytest tests/

# Smoke-test the CLI without touching the GitHub API
PYTHONPATH=src python -m cartouche repo Sandjab/Athanor --mock --theme blueprint-dark --out /tmp/d.svg
PYTHONPATH=src python -m cartouche profile Sandjab --mock --lang fr --out /tmp/p.svg
PYTHONPATH=src python -m cartouche themes
PYTHONPATH=src python -m cartouche langs

# Lint
ruff check .

# Build the wheel (verifies JSON files get packaged)
python -m build
unzip -l dist/cartouche_svg-*.whl | grep '\.json'   # should list en.json, fr.json
```

When testing changes, **always** run `pytest` before declaring done. The
suite catches missing translation keys, broken layouts (well-formed XML),
and regressions in the CLI.

## Architecture invariants

**These are easy to break unintentionally. Hold them sacred.**

1. **Renderers consume tokens, not colors.** `render/primitives.py` and
   `render/repo.py` and `render/profile.py` MUST NOT contain hex codes.
   Every color comes from `theme[token_name]`. Adding a new color to a
   primitive requires adding the token to `themes.py` for ALL 16 themes
   simultaneously (the 10 base themes plus the 6 watermarked variants).

2. **Renderers consume `lang`, not literals.** The renderers MUST NOT
   contain user-visible English/French strings. Every label flows through
   `lang["labels"][key]` (via the `t()` helper) or `lang["templates"][key]`
   (via `tmpl(**kwargs)`). When you add a new label, you add it to BOTH
   `lang/en.json` AND `lang/fr.json`. The test
   `test_lang_has_all_required_keys` enforces this — when it fails it
   tells you exactly which key is missing where.

3. **The data shape is a contract.** `mock.py` and `fetch.py` produce the
   SAME dict shape that `render.repo.render()` and
   `render.profile.render()` consume. The shape is documented as
   `RepoData` and `ProfileData` TypedDicts in the renderers. Changing one
   side requires changing the other and updating `mock.py`.

4. **No JS, no foreignObject, no web fonts.** GitHub's SVG renderer
   strips all of these. The font stack is hardcoded as a system monospace
   fallback in `primitives.MONO_STACK`. Use only basic SVG elements:
   `<rect>`, `<line>`, `<path>`, `<polygon>`, `<circle>`, `<text>`,
   `<pattern>`, `<g>`, `<defs>`.

5. **Stdlib only at runtime.** `pyproject.toml` declares `dependencies = []`.
   `fetch.py` uses `urllib`, `json`, `datetime`. Don't add `requests`,
   `httpx`, `pydantic`, or anything else without a strong reason — the
   appeal of this lib is partly that it installs in 1 second with no
   transitive deps.

## Common tasks

### Adding a new theme

1. Add a key to `THEMES` in `src/cartouche/themes.py`. Mirror the existing
   schema (12 tokens). Naming convention: `<family>-<light|dark>`.
2. Run `pytest tests/test_render.py::test_theme_has_all_tokens` — should
   pass automatically since the new theme will be parametrized in.
3. Optionally regenerate the example SVGs:
   ```bash
   PYTHONPATH=src python -c "from cartouche.render import repo, profile; from cartouche.themes import get_theme; from cartouche.mock import mock_repo, mock_profile; t=get_theme('NEW_THEME'); open('examples/outputs/repo-NEW_THEME.svg','w').write(repo.render(mock_repo(),t))"
   ```

### Adding a new language pack

1. Drop `src/cartouche/lang/<code>.json`. Mirror the schema of `en.json`.
   Every key in `REQUIRED_LANG_LABELS` and `REQUIRED_LANG_TEMPLATES` (see
   `tests/test_render.py`) must be present.
2. Add the file to `pyproject.toml` under
   `[tool.hatch.build.targets.wheel.force-include]` so the wheel ships it.
3. Run `pytest tests/test_render.py::test_lang_has_all_required_keys` —
   parametrized over `lang_module.list_builtin()`, so it picks up the new
   pack automatically.
4. The CLI's `--lang <code>` will work out of the box.

### Adding a new label/template key

1. Add it to `lang/en.json` AND `lang/fr.json` (both, always).
2. Add the key to `REQUIRED_LANG_LABELS` or `REQUIRED_LANG_TEMPLATES` in
   `tests/test_render.py` so its presence is enforced.
3. Use it in the renderer via `t(lang, "key")` or `tmpl(lang, "key", **kwargs)`.
4. Run `pytest`.

### Adding a new dashboard component

The render pipeline is: data dict → primitives → SVG string.

1. Decide if you need a new primitive in `render/primitives.py` (likely
   yes if it's visually distinct). Primitives consume `theme: dict` (and
   `lang: dict` if they emit text).
2. Add a `_fig_<name>(data, theme, lang)` private function in
   `render/repo.py` or `render/profile.py`.
3. Call it from `render(...)` and choose Y coordinates that don't clash
   with existing figs. The current canvas is 680 wide, repo is 760 tall,
   profile is 912 tall. Each renderer's module-level docstring lists the
   y-bands for the existing figs — keep it updated when you move things.
4. Add data shape requirements to the relevant `TypedDict` and produce
   them in BOTH `mock.py` (canned) and `fetch.py` (live).

### Changing the SVG layout

Don't move things by ±2px and call it a day. Test all 16 themes × 2 langs
visually because some text is longer in FR and may overflow. Open one
sample of each in a browser:

```bash
ls examples/outputs/  # 34 samples available
```

The heatmap in particular has tight constraints — its grid is 582px
wide (53 cols × 11px), placed at x=58 to leave 18px gutter for day
labels. Shrinking the canvas means re-fitting the heatmap.

## Things to know about specific files

### `src/cartouche/themes.py`

Sixteen themes in eight light/dark families. The keys MUST match exactly:
`drafting-light`, `drafting-dark`, `blueprint-light`, `blueprint-dark`,
`vellum-light`, `vellum-dark`, `botanical-light`, `botanical-dark`,
`blossom-light`, `blossom-dark`, `vellum-davinci-light`,
`vellum-davinci-dark`, `botanical-floral-light`, `botanical-floral-dark`,
`blossom-kawai-light`, `blossom-kawai-dark`. Tests reference these keys
directly. The watermarked variants are built by `_with_watermark()` from
their parent palette plus a `watermark` token (PNG name, looked up in
`src/cartouche/watermarks/`) and `watermark_opacity`. The default in
`_with_watermark` is 0.10, but each call site overrides it: davinci and
floral run at **0.08**, kawai at **0.05** (kawai art is denser, so a
lower opacity is needed for it to still read as a substrate rather than
as decoration). Note also that the `drafting` family is intentionally
**pure grayscale** — its `data_primary` and `accent` are gray luminance
steps, not hues. Don't "fix" them by reintroducing color.

Adding tokens to a theme: update ALL 16 themes and the
`REQUIRED_THEME_TOKENS` set in tests.

### `src/cartouche/lang/__init__.py`

The `load()` function uses `importlib.resources.files()` for builtin
packs. This means the JSON files MUST be packaged in the wheel. The
`pyproject.toml` does this via `[tool.hatch.build.targets.wheel.force-include]`.
Test by running `python -m build` and inspecting the wheel.

The deep-merge in `_deep_merge()` only merges dicts recursively; lists
and scalars are replaced wholesale. If a user overlay specifies
`"months_short": ["X", "Y"]` (only 2 entries), the renderer will crash
with IndexError when a third month boundary appears. We don't validate
overlays.

### `src/cartouche/fetch.py`

Pure stdlib. Anonymous calls hit the 60 req/h rate limit fast — for
profile dashboards we make ~20+ calls (one stargazers fetch per repo +
languages + commits). Always pass a token in CI.

The two heaviest paths — stargazer timelines and per-repo language
byte counts — go through the disk cache (`cartouche.cache`) via
`_cached_stargazer_dates` / `_cached_languages`. Both `repo_data` and
`profile_data` accept a `cache: Cache | None` arg; when omitted, a
default 24h-TTL cache rooted at `$XDG_CACHE_HOME/cartouche/` is used.
The CLI threads `--no-cache` / `--cache-ttl` / `--cache-dir` into a
`Cache` instance via `_build_cache`.

`_request` raises `fetch.RateLimitError` (subclass of `RuntimeError`)
on 403/429 with `X-RateLimit-Remaining: 0`, with a message that
includes the reset window and an actionable hint when no token is in
play. Other 4xx codes propagate as the original `urllib.error.HTTPError`
unchanged.

The `_count_via_pagination` trick parses the Link header `rel="last"`
to count without iterating. This is faster than full pagination but
relies on GitHub's pagination format. If GitHub ever changes its Link
header format, this breaks; the regex is `re.search(r'<([^>]+)>;\s*rel="last"', ...)`.

The contribution heatmap uses GraphQL (`/graphql` endpoint, not REST)
because the calendar isn't exposed via REST. Requires a token. The
quartile bucketing (line ~370) maps raw counts to 0..4 intensity levels.

### `src/cartouche/render/primitives.py`

These functions return SVG fragments as strings. Composing means
concatenating. Keep that mental model — don't introduce a parsed-tree
representation.

The `line_chart()` function returns a tuple `(svg, project_fn)` so
callers can place annotations using the same coordinate transform that
drew the line. This is intentional. Don't refactor into a class.

`text()` accepts a `letter_spacing` kwarg if you need to deviate from
the role default. Currently used by `notes_block` to tighten the
tracking on bullet rows.

`notes_block` renders one row per note at 8pt with 0.04em tracking,
word-wrapping each note up to `max_lines_per_note` (default 2) via the
private `_wrap_note` helper. If a note still overflows after wrapping,
the last visible line is suffixed with an ellipsis. The default
`max_width_px=372` assumes the cartouche starts at x=420 with an 8px
gap. The block is designed for **≤3 notes**; beyond that it can run
into the credit line at the bottom of the canvas.

### `src/cartouche/render/{repo,profile}.py`

Y coordinates are hardcoded constants. There's no layout engine. If you
move one component, you must move others to avoid collisions. The
constants `CANVAS_W` and `CANVAS_H` at the top are not promises of
parametric layout — they're documentation of what the renderer assumes.
Today: `CANVAS_W=680` for both, `CANVAS_H=760` for repo and `912` for
profile. The profile is 12px taller than the repo on purpose — it gives
the notes block enough room to wrap a long bullet to a 2nd line without
running into the credit line.

Both renderers end with a `P.credit_line(handle, ...)` call that places
a "Proudly Clauded by @<handle>" watermark in the 20-pixel band BELOW
the outer frame (the gap between `frame_y_end` and `canvas_h`). The
handle comes from `data["drawn_by"]` (repo) or `data["handle"]`
(profile), so the watermark adapts to whoever is using the lib. The
string is in `lang["templates"]["proudly_clauded"]` but is intentionally
identical in `en.json` and `fr.json` because "Clauded" is wordplay that
doesn't translate. Users can override via `--lang-file` to remove or
change it.

### `THEMES.md`

The theme catalogue at the repo root. Each preview thumbnail is wrapped
in `<a href="...">` so clicking opens the full-size SVG in a new tab.
**Those links go through jsDelivr** (`cdn.jsdelivr.net/gh/Sandjab/cartouche@main/...`),
not `raw.githubusercontent.com`. The reason is GitHub raw now serves
SVGs with `Content-Security-Policy: default-src 'none'; sandbox`, which
silently blocks the inline `data:image/png;base64,...` watermark
elements — the page renders, but the filigrane disappears. jsDelivr
serves the same files with no such CSP, so the full image is visible.
If you ever swap the CDN, regression-test all three watermarked
families (Vellum + Davinci, Botanical + Floral, Blossom + Kawai).

### `tests/test_render.py`

Parametrized over themes and langs. When adding a new theme or lang the
tests automatically include it. The test count grows multiplicatively
(16 themes × 2 langs × 2 dashboards = 64 render tests; today **170 total**
across `test_render.py` + `test_cache.py` + `test_fetch.py`).

### `tests/test_cache.py`

Pins the contract of `cartouche.cache.Cache` (round-trip, TTL, disabled
mode, version mismatch, path-traversal neutralization, atomic write,
clear-one and clear-all). Also has one integration test that monkey-
patches `_get_paginated` / `_get_json` to raise — proving that a hot
cache really skips the network.

### `tests/test_fetch.py`

Integration coverage for the HTTP layer. Monkey-patches
`urllib.request.urlopen` with a fake response factory so request
construction (UA, Bearer header, API-version pin), every error path
of `RateLimitError` (403/429 with reset window, anon-vs-auth message
variants), and the pagination Link-header chain are exercised without
touching the network.

## Status

| Feature                           | State    |
|-----------------------------------|----------|
| 16 themes (8 families × light/dark, incl. 3 watermarked) | ✅ stable |
| Repo dashboard                    | ✅ stable |
| Profile dashboard                 | ✅ stable |
| i18n with EN+FR + custom overlay  | ✅ stable |
| GitHub Actions workflows          | ✅ stable |
| Tests                             | ✅ 170 passing |
| PyPI release                      | ⏳ not yet pushed |
| Stargazer cache (TTL-based)       | ✅ stable (24h disk cache, --no-cache to skip) |
| Stargazer cache (incremental refresh) | ⏳ planned, not implemented |
| Custom annotation callouts        | ✅ stable via `--annotations-file PATH` (replaces auto-detected first ★ + spike) |
| Multiple layout variants (square, compact) | ⏳ not started |

## Anti-patterns

Things that look reasonable but are wrong:

- ❌ Adding `requests` or `httpx` to dependencies. Use `urllib`.
- ❌ Hardcoding a color (`#1d4ed8`) in a renderer. Use a theme token.
- ❌ Hardcoding a string ("FIG. 01") in a renderer. Use `t()` or `tmpl()`.
- ❌ Embedding a `<style>` tag, JS, or `@font-face` in the SVG. GitHub strips them.
- ❌ Adding to `en.json` only. Both `en.json` and `fr.json` are required.
- ❌ Updating `README.md` and forgetting `README-fr.md` (or vice versa).
  Both files are user-facing; keep them in sync, not literal translations
  of each other but covering the same features.
- ❌ Treating the data dict shape as flexible. It's a contract enforced
  by the TypedDicts and the tests.
- ❌ Making `fetch.py` slower by adding sequential per-repo calls without
  a `max_pages` cap. Profiles with viral repos already take ~1 minute.

## Coding style

- Docstrings are mandatory on public functions and classes. Module-level
  docstrings explain the file's role.
- Type hints everywhere (Python 3.10+ syntax, `list[str]` not `List[str]`).
- 100-char line limit (configured in `[tool.ruff]`).
- F-strings only (no `%` formatting, no `.format()` for non-template
  use cases).
- Dict literals over kwargs to constructors when the dict is data.
- Imports sorted: stdlib, third-party (none here), local relative.

## Cutting a release

The release pipeline is dormant until you push a tag matching `v*`.
Steps to ship a new version:

1. **Land all the changes** that go into the release on `main`. Run
   `pytest` + `ruff check .` + `ruff format --check .` locally.
2. **Bump `version`** in `pyproject.toml` *and* `__version__` in
   `src/cartouche/__init__.py` (these two are the source of truth;
   `fetch.USER_AGENT` reads `__version__`).
3. **Update `CHANGELOG.md`**: rename the topmost `## [Unreleased]`
   section to `## [X.Y.Z] - YYYY-MM-DD`, add a fresh empty
   `## [Unreleased]` above it.
4. **Commit + push** the version + changelog bump to `main`.
5. **Tag**: `git tag vX.Y.Z && git push --tags`. The
   `release.yml` workflow takes it from there:
     - rebuilds wheel + sdist from the tagged commit
     - re-verifies all the packaged resources
     - publishes to PyPI via OIDC trusted publishing (no token)
     - creates a GitHub Release with auto-generated notes attached

For the *first* tag ever, also do the one-time setup documented in
the header comment of `.github/workflows/release.yml` (PyPI Trusted
Publisher + GitHub Environment named `pypi`).

## When in doubt

Read the file. Each module is short enough to understand in one sitting.
The architecture choices are documented inline because we wanted Claude
Code (and humans) to be able to ramp up fast.

If a test fails with an unhelpful message, look at what it asserts — the
parametrized tests usually tell you exactly which theme/lang/key broke.
