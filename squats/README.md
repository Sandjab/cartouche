# Typo-squat placeholders

This directory contains **placeholder packages** that we publish on PyPI under
typo-prone variants of `cartouche-svg`. Each one ships nothing but an
`ImportError` pointing the user at the real project name.

## Why

The "cartouche-svg" PyPI slot also covers `cartouche_svg` and `cartouche.svg`
automatically because PyPI normalises `[-_.]+` → `-` (PEP 503). What it does
**not** cover is concatenated or differently-suffixed variants:

- `cartouchesvg` (no separator) — distinct slot
- `cartouche-py` — distinct slot

Without a defensive presence here, a malicious actor could later publish a
hostile wheel under one of these names targeting users who typo
`pip install` or who copy-paste from an outdated guide.

## What's bundled

Each squat is a 2-file project:

- `src/<modname>/__init__.py` raises a clear `ImportError` at first import
  pointing the user at `cartouche-svg`.
- `pyproject.toml` declares the project with the squatted name, version
  `0.0.1`, no scripts, no runtime deps, MIT (same maintainer / author as
  the real project).

The squats are **never installed** alongside the real `cartouche-svg`; they
are independent PyPI projects sharing nothing but the maintainer.

## How we publish them

These projects are published **once, manually**, via an API token (Trusted
Publishing requires a per-project setup that's overkill for a placeholder
that won't see another upload). Procedure:

```bash
# Generate a PyPI API token at https://pypi.org/manage/account/token/
# (scope: "Entire account" the first time, then narrow down per-project
# afterwards if desired). Export it once for this shell session:
export TWINE_USERNAME=__token__
export TWINE_PASSWORD='pypi-<your-token>'

# Build + upload each squat
for squat in cartouchesvg cartouche-py; do
  (
    cd "squats/$squat"
    rm -rf dist/
    python -m build
    python -m twine upload dist/*
  )
done
```

After the upload, the slot is reserved. We don't iterate on these — if a real
need to ever bump them appears, do it deliberately.

## What we do NOT squat

- `cartouche` (the bare name) — already taken since 2013 by an unrelated
  Sphinx extension, mentioned in `README.md` as a confusion-warning to
  users.
- `cartouche_svg`, `cartouche.svg` — covered automatically by the PEP 503
  normalisation that maps these to `cartouche-svg`.
