# Changelog

All notable changes to Cartouche are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Until the first PyPI release, every entry sits under `[Unreleased]`; once
`v0.2.0` is tagged it will graduate to a dated release section.

## [Unreleased]

Pre-PyPI hardening of v0.2.0. Targeted at first publication.

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

## [0.1.0] - initial scaffold (untagged)

The first public commit set up the project skeleton: pyproject with
zero runtime deps, the original blueprint-only theme set, the repo and
profile dashboard layouts, the GitHub Actions self-hosting workflow,
and the initial sample SVGs. No PyPI release was cut at this stage.
