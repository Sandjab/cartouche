# Multi-language test detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the repo health-radar `tests` axis recognize test files across mainstream languages instead of Python only, so non-Python repos stop rendering a `tests` axis stuck at 0.

**Architecture:** Rewrite `_tree_file_counts` to classify any source file (extension in a flat `CODE_EXTENSIONS` set) and flag it as a test by language-agnostic path/name conventions (`_is_test_path`). Extract the radar's density normalization into a pure `_tests_axis` helper and divide by the new `code` count instead of `py`. No new dependency, one Git Tree call, radar dict shape unchanged.

**Tech Stack:** Python 3.10+, stdlib only (`urllib`, `re`, `warnings`), `pytest` + `monkeypatch`, `ruff` (line-length 100).

**Spec:** `docs/superpowers/specs/2026-06-12-multilang-test-detection-design.md`

**Deviation from spec (flagged):** §4.4 showed the radar `tests` formula inline; this plan extracts it into a pure `_tests_axis(test_count, code_count)` helper for direct unit-testing. Same arithmetic, same result, same radar shape.

---

## File structure

- **Modify** `src/cartouche/fetch.py`
  - Add classification constants (`CODE_EXTENSIONS`, `TEST_DIR_SEGMENTS`, `_SNAKE_DOT_TEST_RE`, `_CAMEL_TEST_RE`) + helpers `_is_test_path`, `_tests_axis`, just above `def _tree_file_counts`.
  - Rewrite `_tree_file_counts` (return `{code, tests, md}`).
  - Update `repo_data`: the `except` fallback dict, drop the `py_count` line, replace the radar `tests` line with `_tests_axis(...)`.
- **Modify** `tests/test_fetch.py` — add a classification + axis test section.
- **Modify** `CHANGELOG.md` — `## [Unreleased]` entry (Task 3).
- **Release only (Task 5, gated):** `pyproject.toml`, `src/cartouche/__init__.py`, `CHANGELOG.md`.

---

## Task 1: Language-agnostic file classification

Rewrite `_tree_file_counts` and add the detection constants + `_is_test_path`. This is the behavioral core; its Python cases double as the backward-compat guard (spec §4.5).

**Files:**
- Modify: `src/cartouche/fetch.py` (constants + `_is_test_path` before `_tree_file_counts` ~line 697; rewrite `_tree_file_counts` lines 697-748)
- Test: `tests/test_fetch.py` (new section appended)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch.py`:

```python
# ──────────────────────────────────────────────────────────────────────────
#  Repo radar file classification (_tree_file_counts)
# ──────────────────────────────────────────────────────────────────────────


def _fake_tree(monkeypatch, blobs, *, extra=(), truncated=False):
    """Patch fetch._get_json to return a fake recursive git tree.

    `blobs` is a list of paths (all type=blob). `extra` injects raw tree
    entries verbatim (e.g. a non-blob). `truncated` sets the API flag.
    """
    tree = {
        "tree": [{"type": "blob", "path": p} for p in blobs] + list(extra),
        "truncated": truncated,
    }
    monkeypatch.setattr(fetch, "_get_json", lambda url, token, accept="": tree)


def test_tree_counts_python(monkeypatch: pytest.MonkeyPatch):
    # Back-compat guard: the legacy Python conventions still classify.
    _fake_tree(
        monkeypatch,
        ["pkg/foo.py", "pkg/test_foo.py", "pkg/foo_test.py",
         "pkg/tests/helper.py", "conftest.py"],
    )
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 5
    assert c["tests"] == 3  # test_foo, foo_test, tests/helper — not conftest/foo


def test_tree_counts_swift_uppercase_dir_and_camel(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["Sources/Proxy.swift", "Tests/ProxyTests.swift"])
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 2
    assert c["tests"] == 1  # Tests/ dir (case-insensitive) + CamelCase suffix


def test_tree_counts_go(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["server.go", "server_test.go"])
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 2
    assert c["tests"] == 1


def test_tree_counts_js_ts(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(
        monkeypatch,
        ["src/app.ts", "src/app.test.ts", "src/util.spec.js", "__tests__/e2e.js"],
    )
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 4
    assert c["tests"] == 3  # .test, .spec, __tests__ dir


def test_tree_counts_ruby(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["lib/user.rb", "spec/user_spec.rb"])
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 2
    assert c["tests"] == 1


def test_tree_counts_rejects_false_positives(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["greatest.py", "contest.go", "latest.js", "manifest.ts"])
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 4
    assert c["tests"] == 0  # no boundary before "test" → not a test


def test_tree_counts_markdown_and_non_code(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(
        monkeypatch,
        ["README.md", "docs/guide.md", "config.json", "logo.svg", ".gitignore"],
    )
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["md"] == 2
    assert c["code"] == 0
    assert c["tests"] == 0


def test_tree_counts_ignores_non_blob_entries(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["a.py"], extra=[{"type": "tree", "path": "pkg"}])
    c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 1


def test_tree_counts_truncated_warns(monkeypatch: pytest.MonkeyPatch):
    _fake_tree(monkeypatch, ["a.py"], truncated=True)
    with pytest.warns(RuntimeWarning, match="truncated"):
        c = fetch._tree_file_counts("o", "n", "main", None)
    assert c["code"] == 1
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && pytest tests/test_fetch.py -k tree_counts -q`
Expected: FAIL — `KeyError: 'code'` (current `_tree_file_counts` returns the `py` key, not `code`).

- [ ] **Step 3: Add constants + `_is_test_path`, then rewrite `_tree_file_counts`**

In `src/cartouche/fetch.py`, insert this block immediately **before** `def _tree_file_counts(`:

```python
# ──────────────────────────────────────────────────────────────────────────
#  File classification for the repo radar's code / tests axes
# ──────────────────────────────────────────────────────────────────────────

# Source-file extensions (no leading dot) used as the language-agnostic
# denominator of the `tests` density axis. Markdown is handled separately
# (docs axis); config/data/asset formats are excluded on purpose. Adding a
# language is a one-line edit here.
CODE_EXTENSIONS = frozenset(
    {
        "py", "pyi", "pyx",
        "swift", "go", "rs",
        "js", "jsx", "mjs", "cjs", "ts", "tsx", "mts", "cts",
        "java", "kt", "kts", "scala", "sc", "rb", "php",
        "c", "h", "cc", "cpp", "cxx", "hpp", "hh", "hxx", "cs", "m", "mm",
        "dart", "ex", "exs", "erl", "hrl", "clj", "cljs", "cljc", "hs", "lua",
        "sh", "bash", "zsh", "pl", "pm", "r", "jl", "groovy", "gradle",
        "vue", "svelte", "fs", "fsx", "ml", "mli", "nim", "zig",
    }
)

# Directory segments that mark a test tree (matched case-insensitively, so
# SwiftPM's `Tests/` and JS `__tests__/` both count).
TEST_DIR_SEGMENTS = frozenset({"test", "tests", "spec", "specs", "__tests__"})

# Name conventions. The mandatory boundary (`_` `.` `-`, or an uppercase
# letter) is what rejects false positives like `greatest`, `contest`,
# `latest`, `manifest`. `_SNAKE_DOT_TEST_RE` runs on the lowercased stem;
# `_CAMEL_TEST_RE` runs on the original stem to require a CamelCase boundary.
_SNAKE_DOT_TEST_RE = re.compile(r"[._-](?:test|spec)s?$")
_CAMEL_TEST_RE = re.compile(r"[a-z0-9](?:Test|Tests|Spec|Specs)$")


def _is_test_path(segs: list[str], stem: str) -> bool:
    """True if a code file looks like a test, by directory or by name.

    `segs` is the path split on '/'; `stem` is the basename without its
    extension. Directory match wins first (any parent segment is a test
    dir), then the name conventions.
    """
    if any(s.lower() in TEST_DIR_SEGMENTS for s in segs[:-1]):
        return True
    sl = stem.lower()
    if sl in ("test", "tests", "spec", "specs"):
        return True
    if sl.startswith("test_"):
        return True
    if _SNAKE_DOT_TEST_RE.search(sl):
        return True
    if _CAMEL_TEST_RE.search(stem):
        return True
    return False
```

Then **replace** the entire `_tree_file_counts` function body (currently lines 697-748) with:

```python
def _tree_file_counts(owner: str, name: str, branch: str, token: str | None) -> dict[str, int]:
    """Count code, test, and Markdown files at the tip of `branch`.

    One recursive Git Tree call, feeding the repo radar's `tests` and `docs`
    axes. Replaces the Code Search–based estimators that preceded this: the
    search index lags fresh commits and rate-limits aggressively, and the
    old code silently treated every error as 0.

    Returns a dict with keys "code", "tests", "md".

    Classification is language-agnostic:
      - basename ending in `.md`                 → "md"
      - extension in `CODE_EXTENSIONS`           → "code", and additionally
        "tests" when `_is_test_path` matches (a test directory, or a name
        convention such as `test_*`, `*_test`, `*.spec`, `FooTests`)
      - anything else (configs, assets, …)       → ignored

    For very large repos (>100k entries) the Git Tree API truncates its
    response; we emit a `RuntimeWarning` and return the counts seen so far,
    which are then lower bounds rather than exact values.
    """
    safe_branch = urllib.parse.quote(branch, safe="")
    url = f"{API_BASE}/repos/{owner}/{name}/git/trees/{safe_branch}?recursive=1"
    data = _get_json(url, token)

    counts = {"code": 0, "tests": 0, "md": 0}
    for entry in data.get("tree", []):
        if entry.get("type") != "blob":
            continue
        path = entry.get("path", "")
        segs = path.split("/")
        basename = segs[-1]
        if basename.endswith(".md"):
            counts["md"] += 1
            continue
        dot = basename.rfind(".")
        ext = basename[dot + 1 :].lower() if dot > 0 else ""
        if ext in CODE_EXTENSIONS:
            counts["code"] += 1
            if _is_test_path(segs, basename[:dot]):
                counts["tests"] += 1

    if data.get("truncated"):
        warnings.warn(
            f"cartouche: git tree for {owner}/{name} was truncated; "
            "tests/docs counts are lower bounds",
            RuntimeWarning,
            stacklevel=2,
        )
    return counts
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && pytest tests/test_fetch.py -k tree_counts -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
git add src/cartouche/fetch.py tests/test_fetch.py
git commit -m "fix: detect test files across languages, not just Python"
```

---

## Task 2: Radar normalization via `_tests_axis`

Extract the density formula and divide by the new `code` count.

**Files:**
- Modify: `src/cartouche/fetch.py` (add `_tests_axis`; update `repo_data` fallback dict line ~145, drop `py_count` line ~146, radar `tests` line ~154)
- Test: `tests/test_fetch.py` (append axis tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_fetch.py`:

```python
# ──────────────────────────────────────────────────────────────────────────
#  Tests-axis normalization (_tests_axis)
# ──────────────────────────────────────────────────────────────────────────


def test_tests_axis_zero_when_no_code():
    assert fetch._tests_axis(0, 0) == 0.0
    assert fetch._tests_axis(5, 0) == 0.0  # guard: no recognized code → 0


def test_tests_axis_zero_when_no_tests():
    assert fetch._tests_axis(0, 10) == 0.0


def test_tests_axis_saturates_at_thirty_percent():
    assert fetch._tests_axis(3, 10) == 1.0    # 3 / (10*0.3) = 1.0
    assert fetch._tests_axis(78, 160) == 1.0  # Iris case, well above 30%


def test_tests_axis_partial_density():
    assert fetch._tests_axis(1, 10) == pytest.approx(1 / 3.0)  # 1 / (10*0.3)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && pytest tests/test_fetch.py -k tests_axis -q`
Expected: FAIL — `AttributeError: module 'cartouche.fetch' has no attribute '_tests_axis'`.

- [ ] **Step 3: Add `_tests_axis` and wire it into `repo_data`**

In `src/cartouche/fetch.py`, add this helper just after `_is_test_path` (before `_tree_file_counts`):

```python
def _tests_axis(test_count: int, code_count: int) -> float:
    """Repo radar `tests` axis: a density proxy of test files relative to
    code files, saturating at a 30% ratio. Zero when no recognized code
    exists (avoids division by zero; 'no code' → 'no test signal')."""
    if not code_count:
        return 0.0
    return min(1.0, test_count / max(1, code_count * 0.3))
```

In `repo_data`, change the `except` fallback dict (currently line ~145) from:

```python
        counts = {"py": 0, "tests": 0, "md": 0}
    py_count = counts["py"]
```

to:

```python
        counts = {"code": 0, "tests": 0, "md": 0}
```

(Delete the `py_count = counts["py"]` line entirely.)

Then change the radar `tests` line (currently line ~154) from:

```python
        "tests": min(1.0, counts["tests"] / max(1, py_count * 0.3)) if py_count else 0.0,
```

to:

```python
        "tests": _tests_axis(counts["tests"], counts["code"]),
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && pytest tests/test_fetch.py -q`
Expected: PASS — the full `test_fetch.py` suite is green (no reference to the old `py` count remains; `repo_data` still imports/uses `counts["code"]`).

- [ ] **Step 5: Commit**

```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
git add src/cartouche/fetch.py tests/test_fetch.py
git commit -m "fix: divide tests axis by language-agnostic code count"
```

---

## Task 3: Changelog entry

Document the change under `[Unreleased]` (Keep a Changelog, per the repo's CHANGELOG format). The `_tree_file_counts` docstring was already rewritten in Task 1.

**Files:**
- Modify: `CHANGELOG.md` (the `## [Unreleased]` section near the top)

- [ ] **Step 1: Add the changelog entry**

In `CHANGELOG.md`, replace:

```markdown
## [Unreleased]
```

with:

```markdown
## [Unreleased]

### Fixed

- The repo health-radar **tests** axis now recognizes test files across
  languages (Swift, Go, Rust, JS/TS, Java, Kotlin, Ruby, …) instead of
  Python only, so non-Python repositories no longer render a `tests` axis
  stuck at 0. Detection uses language-agnostic path/name conventions and
  the axis stays a density proxy saturating at a 30% test-to-code ratio.
```

- [ ] **Step 2: Verify (no test; lint only)**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && ruff check . && pytest -q`
Expected: ruff clean, full suite PASS (was 147 tests, now ~160).

- [ ] **Step 3: Commit**

```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
git add CHANGELOG.md
git commit -m "docs: changelog entry for the multi-language tests axis"
```

---

## Task 4: Gate + open the PR

**Files:** none (CI/PR only)

- [ ] **Step 1: Full local gate**

Run: `cd /Users/jean-paulgavini/Documents/Dev/cartouche && ruff check . && pytest -q`
Expected: ruff clean, all tests PASS.

- [ ] **Step 2: Optional real-API smoke (needs network; a token avoids the 60/h anon limit)**

Run:
```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
python -m cartouche repo Sandjab/Iris --theme blueprint-light --out /tmp/iris.svg
```
Expected: SVG written; the radar's TESTS axis is now non-zero (Iris is Swift). Compare against the live 0% to confirm the fix end-to-end.

- [ ] **Step 3: Push the branch and open the PR**

```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
git push -u origin feat/multilang-test-detection
gh pr create --title "fix: multi-language test detection for the repo health radar" \
  --body "$(cat <<'EOF'
Fixes the repo radar `tests` axis reading 0 on non-Python repos (e.g. Swift `Sandjab/Iris`).
`_tree_file_counts` now classifies any source file and flags tests by language-agnostic
path/name conventions; the axis is normalized against a language-agnostic code count via
the new `_tests_axis` helper. Radar shape unchanged.

Spec: docs/superpowers/specs/2026-06-12-multilang-test-detection-design.md

### Smoke checklist
- [ ] `ruff check .` clean
- [ ] `pytest` green (147 → ~160)
- [ ] `cartouche repo Sandjab/Iris` renders a non-zero TESTS axis
- [ ] Pure-Python repo (cartouche itself) TESTS axis not regressed
EOF
)"
```

- [ ] **Step 4: Gemini / review handling** — address review comments (apply or factually refuse), then request explicit user confirmation before merge. Squash-merge on approval.

---

## Task 5 (gated): Release 0.3.1 to PyPI

> **Do NOT run this task until the fix PR is merged to `main` AND the user explicitly confirms cutting the release.** Publishing to PyPI via the `v*` tag is irreversible.

**Files:**
- Modify: `pyproject.toml` (line 7 `version`), `src/cartouche/__init__.py` (line 9 `__version__`), `CHANGELOG.md`

- [ ] **Step 1: Bump version (both must match — `fetch.USER_AGENT` reads `__version__`)**

In `pyproject.toml`: `version = "0.3.0"` → `version = "0.3.1"`.
In `src/cartouche/__init__.py`: `__version__ = "0.3.0"` → `__version__ = "0.3.1"`.

- [ ] **Step 2: Promote the changelog**

In `CHANGELOG.md`, change `## [Unreleased]` (with its `### Fixed` block from Task 3) to `## [0.3.1] - 2026-06-12`, and add a fresh empty `## [Unreleased]` above it.

- [ ] **Step 3: Verify + commit + tag (after explicit confirmation)**

```bash
cd /Users/jean-paulgavini/Documents/Dev/cartouche
ruff check . && pytest -q
git add pyproject.toml src/cartouche/__init__.py CHANGELOG.md
git commit -m "chore: release 0.3.1"
git push origin main
git tag v0.3.1 && git push --tags   # triggers release.yml → PyPI via OIDC
```
Expected: `release.yml` builds wheel+sdist and publishes `cartouche-svg==0.3.1`, and creates the GitHub Release. Iris `dashboard.yml` (`pip install cartouche-svg`) picks it up on its next scheduled run (≤6h).

---

## Self-review

- **Spec coverage:** §4.1→Task 1 (`_tree_file_counts`); §4.2 `CODE_EXTENSIONS`→Task 1; §4.3 detection→Task 1 (`_is_test_path`); §4.4 radar→Task 2 (`_tests_axis` + `repo_data`); §4.5 back-compat→`test_tree_counts_python` (Task 1); §5 test cases 1-10→Tasks 1-2 tests; §6 docs→Task 1 docstring + Task 3 changelog; §7 distribution→Tasks 4-5. No gaps.
- **Placeholder scan:** none — every code/command step is concrete.
- **Type consistency:** counts keys `code`/`tests`/`md`, `_is_test_path(segs, stem)`, `_tests_axis(test_count, code_count)` used consistently across Tasks 1-2.
- **Flagged deviation:** `_tests_axis` extraction vs spec's inline formula (testability; identical behavior).
