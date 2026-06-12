# Multi-language test detection for the repo health radar

- **Date:** 2026-06-12
- **Status:** Approved (design) — pending implementation plan
- **Component:** `src/cartouche/fetch.py` (`_tree_file_counts`, `repo_data` radar)
- **Target release:** `cartouche-svg` 0.3.1

## 1. Problem

The repo dashboard's `FIG. 02` health radar has six axes: stars, forks,
commits, code, **tests**, docs. The `tests` axis reads ~0 on every
non-Python repository, regardless of how thoroughly it is tested.

Root cause is in `_tree_file_counts` + the radar normalization:

- `_tree_file_counts` only ever classifies `.py` files. It returns
  `{"py", "tests", "md"}`, and a file counts as a test only if it is a
  `.py` whose path has a `tests/` segment, or whose basename starts with
  `test_` / ends with `_test.py`.
- The radar line:
  ```python
  "tests": min(1.0, counts["tests"] / max(1, py_count * 0.3)) if py_count else 0.0,
  ```
  short-circuits to `0.0` whenever `py_count == 0`.

So any repo with zero `.py` files gets `tests = 0`, even though the
sibling `code` axis is language-agnostic (it sums `lang_bytes` from the
GitHub `/languages` endpoint and happily reaches 100% on Swift, Go, etc.).

**Observed example.** `Sandjab/Iris` is ~96% Swift with 78 test files
against 82 source files (a ~1:1 test-to-source ratio), yet its rendered
radar shows `code = 100%`, `docs = 100%`, `tests = 0%`. The 0 is an
artifact of a Python-only detector, not a property of the repo.

This is an asymmetry, not a one-off: every non-Python repo that embeds a
cartouche dashboard hits it.

## 2. Goals / non-goals

**Goals**

- Make the `tests` axis meaningful across mainstream languages using a
  single, language-agnostic detection rule (no per-language table).
- Preserve the existing *semantics* of the axis: a density proxy
  (test files relative to code files), saturating at the same 30%
  threshold.
- Preserve backward compatibility for pure-Python repos: their score must
  not regress.
- Keep the module's constraints: stdlib-only, one recursive Git Tree call,
  no new dependency.

**Non-goals**

- Real code coverage (`llvm-cov`/`coverage.py` percentages). The axis
  stays a cheap file-count proxy — a "vital sign", not a coverage report.
- Changing the `code` axis (stays `sum(lang_bytes) / 500_000`) or the
  `docs` axis (stays `md_count / 8`).
- Touching the profile radar (`reach/activity/breadth/depth/polyglot/
  engagement` — it has no `tests` axis).
- Changing `mock.py`, the SVG renderer, or the README. The `radar` dict
  shape is unchanged; only the *values* move.

## 3. Decisions

1. **Universal naming conventions, not a per-language table.** Tests are
   detected by path/name conventions applied to any code file, rather than
   a `{language → (extensions, test patterns)}` map. Chosen for zero
   maintenance as new languages appear, at the cost of accepting a little
   noise (a helper named `TestSupport.swift` outside a test directory will
   count). Fits the "lower bound / indicative radar" spirit already stated
   in the `_tree_file_counts` docstring.
2. **Denominator becomes a language-agnostic code-file count.** The radar
   ratio divides by `code_count` (files whose extension is in a flat
   `CODE_EXTENSIONS` set) instead of `py_count`. This set is the only
   residual "list", and it feeds the *denominator* only — test detection
   itself stays name/path-based.
3. **Density semantics and the 0.3 threshold are unchanged.** Same formula
   shape, `py_count` → `code_count`.

## 4. Detailed design

### 4.1 `_tree_file_counts` — new classification

Return shape changes from `{"py", "tests", "md"}` to
`{"code", "tests", "md"}`. For each `blob` entry in the recursive tree:

```python
basename = segs[-1]
dot = basename.rfind(".")
ext = basename[dot + 1:].lower() if dot > 0 else ""   # dot>0 keeps dotfiles ext-less
stem = basename[:dot] if dot > 0 else basename

if basename.endswith(".md"):
    counts["md"] += 1
    continue
if ext in CODE_EXTENSIONS:
    counts["code"] += 1
    if _is_test_path(segs, stem):
        counts["tests"] += 1
```

`.md` is handled before the code branch (unchanged docs behavior). Files
whose extension is not in `CODE_EXTENSIONS` are neither code nor tests
(conservative: an exotic-language test file is not counted as a test, but
it is not counted as code either, so the ratio stays coherent).

### 4.2 `CODE_EXTENSIONS`

A flat, extensible `frozenset` of source extensions (without the dot),
covering the mainstream stack. Initial set:

```
py pyi pyx  swift  go  rs
js jsx mjs cjs  ts tsx mts cts
java  kt kts  scala sc  rb  php
c h  cc cpp cxx hpp hh hxx  cs  m mm
dart  ex exs  erl hrl  clj cljs cljc  hs  lua
sh bash zsh  pl pm  r  jl  groovy gradle
vue svelte  fs fsx  ml mli  nim  zig
```

Explicitly excluded: `.md` (docs), config/data formats (`json`, `yaml`,
`yml`, `toml`, `ini`, `xml`, `txt`), assets, lockfiles. Adding a language
later is a one-line edit to this set.

### 4.3 Test-path detection

```python
TEST_DIR_SEGMENTS = frozenset({"test", "tests", "spec", "specs", "__tests__"})
_SNAKE_DOT_TEST_RE = re.compile(r"[._-](?:test|spec)s?$")        # case-insensitive input
_CAMEL_TEST_RE     = re.compile(r"[a-z0-9](?:Test|Tests|Spec|Specs)$")  # case-sensitive

def _is_test_path(segs: list[str], stem: str) -> bool:
    # (a) any directory segment is a test dir (case-insensitive → catches SwiftPM `Tests/`)
    if any(s.lower() in TEST_DIR_SEGMENTS for s in segs[:-1]):
        return True
    sl = stem.lower()
    # (b) name conventions
    if sl in ("test", "tests", "spec", "specs"):
        return True
    if sl.startswith("test_"):                 # Python: test_foo
        return True
    if _SNAKE_DOT_TEST_RE.search(sl):          # foo_test, foo.test, bar_spec, x.spec
        return True
    if _CAMEL_TEST_RE.search(stem):            # FooTest(s), BarSpec (CamelCase, case-sensitive)
        return True
    return False
```

The mandatory boundary (`_`, `.`, `-`, or an uppercase letter before
`Test`/`Spec`) is what rejects false positives like `greatest`,
`contest`, `latest`, `manifest`.

Worked examples:

| Path | code? | test? | Why |
|---|---|---|---|
| `Sources/Proxy.swift` | ✅ | ❌ | code, no test marker |
| `Tests/ProxyTests.swift` | ✅ | ✅ | `Tests/` dir **and** `…Tests` camel |
| `proxy_test.go` | ✅ | ✅ | `_test` snake suffix |
| `api/foo.test.ts` | ✅ | ✅ | `.test` dotted suffix |
| `spec/user_spec.rb` | ✅ | ✅ | `spec/` dir **and** `_spec` suffix |
| `__tests__/widget.js` | ✅ | ✅ | `__tests__` dir |
| `test_parser.py` | ✅ | ✅ | `test_` prefix |
| `greatest.py` / `contest.go` / `latest.js` | ✅ | ❌ | no boundary before `test` |
| `manifest.ts` | ✅ | ❌ | ends `…fest`, not `…test` |
| `README.md` | ❌ | ❌ | docs (`md` branch) |
| `config.json` / `logo.svg` | ❌ | ❌ | not in `CODE_EXTENSIONS` |

### 4.4 Radar normalization

```python
code_count = counts["code"]
radar = {
    ...
    "code":  min(1.0, sum(lang_bytes.values()) / 500_000),   # unchanged
    "tests": min(1.0, counts["tests"] / max(1, code_count * 0.3)) if code_count else 0.0,
    "docs":  min(1.0, counts["md"] / 8),                     # unchanged
}
```

Only `py_count` → `code_count`. The `if code_count else 0.0` guard is kept
(a repo with no recognized code file → axis 0, no division by zero). The
`except urllib.error.HTTPError` fallback dict in `repo_data` becomes
`{"code": 0, "tests": 0, "md": 0}`.

### 4.5 Backward compatibility

For a pure-Python repo: `code_count == py_count` (only `.py` in the set
among its files), and every previously-recognized test still matches
(`test_*`, `*_test.py`, `tests/` dir), plus a few new ones (`*_spec.py`,
`FooTest.py`). So the score is identical or slightly higher — never
broken. For `Sandjab/Iris`: 78 tests / ~160 code files ≈ 49% → above the
30% saturation → **100%**.

## 5. Tests (TDD)

`_tree_file_counts` currently has **no dedicated test**. Add a section to
`tests/test_fetch.py` that monkeypatches `fetch._get_json` to return a
canned `{"tree": [...], "truncated": ...}` and asserts the returned
counts. Cases:

1. **Python** — `test_foo.py`, `foo_test.py`, `pkg/tests/x.py` counted as
   tests; `conftest.py` and `pkg/foo.py` not.
2. **Swift** — `Sources/A.swift` code-only; `Tests/ATests.swift` test
   (dir + camel); verifies the case-insensitive `Tests/` match.
3. **Go** — `a.go` code-only; `a_test.go` test.
4. **JS/TS** — `a.ts` code-only; `a.test.ts`, `b.spec.js`,
   `__tests__/c.js` tests.
5. **Ruby** — `a.rb` code-only; `spec/a_spec.rb` test.
6. **False positives** — `greatest.py`, `contest.go`, `latest.js`,
   `manifest.ts` counted as code but **not** tests.
7. **Docs/non-code** — `README.md` → md; `config.json`, `logo.svg` →
   neither code nor md nor tests.
8. **Empty / no code** — tree with only docs/config → `code == 0`, and
   (integration-light) the resulting `tests` axis is `0.0` via the guard.
9. **Truncated** — `truncated: true` emits a `RuntimeWarning`
   (`pytest.warns`), counts are still returned.
10. **Backward-compat** — a pure-Python tree yields the same `tests`/code
    ratio as the legacy `py`-based logic for an equivalent input.

`ruff check .` and `pytest` must pass (project gate per `CONTRIBUTING.md`).

## 6. Documentation to update

- Rewrite the `_tree_file_counts` docstring (new classification rules,
  `{code, tests, md}` shape).
- Adjust the comment block above the `counts = _tree_file_counts(...)` call
  in `repo_data` (currently says "tests/docs radar axes" / Python-centric).
- No README / `mock.py` / renderer change (radar shape unchanged).

## 7. Distribution & release

Per `cartouche/CLAUDE.md` §"Cutting a release":

1. Branch `feat/multilang-test-detection` off `cartouche:main`.
2. Implement (TDD), `ruff check .` + `pytest` green locally.
3. PR → `cartouche:main`, squash-merge on explicit user confirmation.
4. Bump `version` in `pyproject.toml` and `__version__` in
   `src/cartouche/__init__.py` to **0.3.1**.
5. CHANGELOG: promote `## [Unreleased]` → `## [0.3.1] - 2026-06-12`
   (the release date; adjust if the tag is cut later) with a `### Fixed`
   entry describing the multi-language `tests` axis.
6. Tag `v0.3.1` + push → `release.yml` builds and publishes to PyPI via
   OIDC trusted publishing, and creates a GitHub Release.

**The tag/publish step happens only on explicit user confirmation at that
moment** — publishing to PyPI is irreversible. Once published, the Iris
`dashboard.yml` (`pip install cartouche-svg`) picks up 0.3.1 on its next
scheduled run (every 6h), and the Iris radar's `tests` axis renders for
real. No change to the Iris repo is required.

Version choice: **0.3.1** (PATCH) — a behavior correction with no public
API change. `0.4.0` would be defensible if treated as a feature; left for
the user to confirm at review.

## 8. Risks & limitations

- **Accepted noise:** non-test files named `*Test*`/`*Spec*` outside a test
  directory count as tests. Acceptable for an indicative radar.
- **Exotic extensions** absent from `CODE_EXTENSIONS` make a repo's code
  (and tests) invisible to the axis — same failure mode as today for the
  unlisted language, but now a one-line fix. Mitigated by a broad initial
  set.
- **Convention-less test setups** (e.g. Rust `#[cfg(test)]` inline modules
  with no dedicated file, doctests) are not detected — a fundamental limit
  of file-name heuristics, out of scope.
- The axis remains a **density proxy**, never a coverage measurement.
