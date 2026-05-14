# Changelog

All notable changes to Cartouche are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.2] - 2026-05-14

### Fixed

- `cartouche.fetch` no longer flips the repo radar's tests and docs
  axes to `0` on roughly one refresh in three. The two prior estimators
  (`_estimate_tests_ratio`, `_estimate_docs_ratio`) counted matching
  files via GitHub's Code Search API and silently caught every
  `urllib.error.HTTPError` as `return 0.0`. Code Search lags fresh
  commits, rate-limits aggressively, and 5xx's regularly — each of
  those produced a zeroed radar with no log and no warning. Replaced
  by a single recursive Git Tree call against the repo's default
  branch (`_tree_file_counts`), which is deterministic against the
  live HEAD and bypasses the search index entirely. `HTTPError` now
  propagates from the helper; `repo_data` catches it once and falls
  back to `0/0` with an explicit `RuntimeWarning`, so silent zeros
  are gone. Behaviour pinned by four new tests in
  `tests/test_fetch.py` (classification, URL branch encoding,
  truncation warning, error propagation).

## [0.2.1] - 2026-05-11

### Fixed

- `cartouche.fetch._detect_annotations` no longer crashes with
  `TypeError: '<' not supported between instances of 'dict' and 'dict'`
  when two consecutive star-history points produce the same delta. The
  sort now pins its comparison key to the delta itself, so Python never
  falls through to comparing the dict payloads. This was the root cause
  of failures in the bundled `repo-dashboard.yml` GitHub Action
  workflow's *Render light + dark variants* step. Regression pinned by
  `test_detect_annotations_tied_deltas_do_not_compare_dicts` (#7).

## [0.2.0] - 2026-05-10

First PyPI release.

### Added

- **Two dashboard composers**: `cartouche.render.repo` and
  `cartouche.render.profile`, fed by a `RepoData` / `ProfileData` dict
  contract produced by either `cartouche.fetch` (live) or
  `cartouche.mock` (canned).
- **Sixteen themes** across eight families: five clean palettes
  (drafting, blueprint, vellum, botanical, blossom) plus three
  watermarked variants (vellum + davinci, botanical + floral, blossom +
  kawai), each in light and dark.
- **Internationalization**: English + French built-in packs, with
  `--lang-file` JSON overlay support that deep-merges on top of the
  base pack.
- **Custom star-history annotations** via `--annotations-file PATH` on
  the repo dashboard, replacing the auto-detected first ★ + spike pair
  with a user-supplied event list.
- **Watermark layer** for the three watermarked families: a bundled PNG
  (Da Vinci plate, floral motif, kawaii character) embedded inline as a
  base64 `data:` URI, sitting behind the data layer at low opacity.
- **README sampler**: five light-theme thumbnails under the hero,
  linking to their respective sections in `THEMES.md`.
- **Documentation**: `THEMES.md` catalogue (every variant, light + dark,
  with per-family rationale), `CLAUDE.md` handoff for AI-assisted
  contributions, English + French READMEs in lock-step.
- **CI workflow**: matrix Python 3.10 – 3.13, ruff + pytest, plus a
  separate `build-wheel` job that verifies the language packs and
  watermark PNGs are packaged into the wheel.
- **Visitors badge** (komarev), one counter per repo.
- **Disk cache** (`cartouche.cache.Cache`) for the two GitHub endpoints
  that dominate runtime: stargazer timelines and per-repo language
  byte counts. JSON-on-disk under `$XDG_CACHE_HOME/cartouche/` with a
  24h TTL by default. New CLI flags: `--no-cache`, `--cache-ttl
  SECONDS`, `--cache-dir PATH`. A second `cartouche profile` run on
  the same handle is now near-instant.
- **`py.typed` marker** (PEP 561): downstream type-checkers
  (mypy, pyright) now trust the inline type hints, so consumers of
  `cartouche.fetch` / `cartouche.render` get full IDE completion.
- **Sample overlays** under `examples/`: a lang overlay
  (`examples/lang/_overlay.json`) and a custom-annotations file
  (`examples/annotations/sample.json`) — copy-paste starting points
  for the `--lang-file` and `--annotations-file` flags.
- **`fetch.RateLimitError`**: a dedicated exception (subclass of
  `RuntimeError`) raised when GitHub returns 403/429 with
  `X-RateLimit-Remaining: 0`. The message is actionable: it includes
  the time-to-reset (parsed from `X-RateLimit-Reset`) and, for
  anonymous calls, suggests setting `GITHUB_TOKEN` / `--token` to
  raise the limit from 60/h to 5000/h.
- **Project hygiene files**: `SECURITY.md` (private vulnerability
  reporting + threat model), `CONTRIBUTING.md` (front-door for new
  contributors), `.github/ISSUE_TEMPLATE/{bug_report,feature_request,config}.yml`,
  and `.pre-commit-config.yaml` (ruff check + ruff format + generic
  hygiene hooks for local pre-commit runs).
- **`tests/test_fetch.py`** (23 new tests): integration-flavored
  coverage for the HTTP layer with `urllib.request.urlopen` monkey-
  patched. Exercises request construction (User-Agent, Bearer token,
  API version pin), rate-limit detection (every error path of the
  new `RateLimitError`), pagination (Link header chain, max_pages
  cap, `_count_via_pagination`), and token resolution priority.

### Changed

- **Drafting** flips from a slate-blue/orange palette to **pure
  grayscale**; series and accent are now separated by lightness only.
- **Lighter backgrounds** on botanical-light (`#f3efde` → `#faf6ed`) and
  blossom-light (`#fff5f8` → `#fefafc`) for a less saturated paper.
- **Per-family watermark opacities** instead of the flat 0.10 default:
  davinci 0.08, floral 0.08, kawai 0.05 (kawai art is denser, needs
  more pull-back to read as substrate).
- **Profile canvas height** 900 → 912 to leave room for the notes block
  to wrap a long bullet to a second line without running into the
  credit line.
- **Notes block** rendered at 8 pt with `0.04em` letter-spacing (was
  9 pt / `0.08em`), word-wrapped to at most two lines per note, with
  ellipsis truncation if a note still overflows.
- **`primitives.text()`** accepts a `letter_spacing` kwarg for per-call
  overrides of the role default.
- **THEMES.md preview links** point at jsDelivr (`cdn.jsdelivr.net/gh/...`)
  rather than `raw.githubusercontent.com`. Raw GitHub now serves SVGs
  with `Content-Security-Policy: default-src 'none'; sandbox`, which
  silently blocks inline `data:` watermark images; jsDelivr serves the
  same files unrestricted.
- **README structure**: `What gets displayed` moved up to right after
  `Why`, contents/sommaire TOC at the top, install caveat noting the
  PyPI release is still pending.

### Fixed

- Two unused imports surfaced by ruff once the CI started enforcing it
  (`collections.defaultdict` in `fetch.py`, `typing.Iterable` in
  `primitives.py`).
- B904: chained exceptions (`raise ... from None`) in CLI error paths
  and in `lang.t` / `lang.tmpl`, so user-facing error output isn't
  noised up by an internal-traceback chain.
- B023: a nested `box(anchor, leader_y)` function in
  `render.repo._layout_annotations` was closing over the loop variables
  `sx` and `label_w`. Even though it was called within the same
  iteration, the lint surfaces a real footgun pattern; binding both
  via default arguments captures the per-iteration values explicitly.

### Infra

- **PyPI release prep**: dormant `release.yml` workflow that ships
  the wheel + sdist via OIDC trusted publishing on `git tag v*`, plus
  a CHANGELOG.md and the install caveat in the README until v0.2.0
  actually lands on PyPI.
- **Stricter ruff config**: `[tool.ruff.lint]` selects
  `["E", "F", "W", "I", "B", "UP"]` (pycodestyle + pyflakes + isort +
  bugbear + pyupgrade), keeping the lint floor consistent across the
  Python 3.10 – 3.13 matrix.
- **CI: smoke-install from sdist** in addition to wheel verification,
  so the very `pip install cartouche_svg-X.tar.gz` path that PyPI
  consumers will hit is tested on every push.
- **`pyproject.toml`** modernized for the upcoming release:
  Development Status moves from `3 - Alpha` to `4 - Beta`, Python 3.13
  classifier added, `Typing :: Typed` classifier added, project URLs
  extended with Changelog / Themes / Documentation.

### Security

A pre-publication audit shaped the security baseline of this first
release. Surfaced and fixed before any wheel left CI:

- **`lang.tmpl` format-string sandbox** (`_SafeFormatter`): a malicious
  `--lang-file` overlay can no longer introspect kwargs via attribute
  or item access (`{date.__class__.__mro__}`-style probes). Plain
  placeholders like `{n}` continue to work; anything containing `.` or
  `[` is rejected with a clear `ValueError`.
- **GitHub-safe segment validation** (`fetch._validate_segment`): every
  `owner` / `repo name` / `handle` flowing into an interpolated f-string
  URL is matched against `^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$`. A
  smuggled value like `foo/../search/code?q=secret` is rejected before
  any HTTP request is built.
- **GraphQL variables, not string interpolation**: the contribution-
  calendar query passes `handle` as a `$login: String!` variable.
  Closes alias-smuggling and complexity-DoS via crafted handles.
- **Cross-host redirect blocking** (`fetch._SameHostRedirectHandler`):
  redirects to any host other than `api.github.com` are refused, so
  the bearer token never travels along an unexpected hop.
- **Supply-chain hardening of the release pipeline**: every third-party
  GitHub Action is SHA-pinned (with the previous tag in a trailing
  comment), Dependabot keeps those pins current, and
  `permissions: contents: read` is declared at the workflow level on
  `ci.yml` and `release.yml` so jobs default to read-only and have to
  opt in for more.
- **Defense-in-depth elsewhere**: example workflows demonstrate the
  `env: REPO/OWNER` pattern instead of splicing
  `${{ github.repository }}` directly into `run:` blocks; `.gitignore`
  covers `.env*`, `*.pem`, `*.key`, IDE configs, and OS files.

Coverage: 36 new tests in `test_render.py` + `test_fetch.py` exercise
every fix above (170 → 206 passing).

## [0.1.0] - initial scaffold (untagged)

The first public commit set up the project skeleton: pyproject with
zero runtime deps, the original blueprint-only theme set, the repo and
profile dashboard layouts, the GitHub Actions self-hosting workflow,
and the initial sample SVGs. No PyPI release was cut at this stage.
