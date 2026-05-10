# Security policy

## Reporting a vulnerability

If you find a security issue in Cartouche, please report it privately
rather than in a public GitHub issue.

- **Preferred channel**: open a [private security advisory](https://github.com/Sandjab/cartouche/security/advisories/new)
  on the repository (GitHub will notify the maintainer and keep the
  thread out of the public timeline).
- **Alternative**: email the maintainer at <consulting@gavini.org>
  with `[cartouche]` in the subject.

Please include:

1. A description of the issue and where it lives in the codebase
   (file + roughly the function or block).
2. The conditions required to trigger it (input shape, environment,
   minimum lib version).
3. The impact you observed or expect (data exfiltration, code
   execution, denial of service, etc.).
4. If possible, a minimal reproduction — command line invocation +
   the input that triggers the issue.

You should hear back within **a few days**. If the report is accepted,
expect a coordinated disclosure: a fix is prepared and released as a
patch version, then the advisory is published and credit is offered
(opt-in).

## Threat model

Cartouche is a code-generation library, not a service. The relevant
attack surface is:

| Surface | Notes |
|---|---|
| `--lang-file` JSON overlay | Loaded and deep-merged. We do not `eval`/`exec` overlay content; the only execution happens via `str.format(**kwargs)` on template strings. A malicious overlay can produce nonsense rendering, but should not run arbitrary code. |
| `--annotations-file` JSON | Strict shape validation in CLI; fails closed. |
| `cartouche.fetch` | Talks to `api.github.com` over HTTPS; no other network destinations. The bearer token is only sent in the `Authorization` header. |
| `cartouche.cache` | Writes JSON files under `$XDG_CACHE_HOME/cartouche/`. Path parts derived from API responses are sanitized so they can't escape `base_dir` via `..` or `/`. |
| Generated SVGs | Pure SVG primitives — no `<script>`, no `<foreignObject>`, no embedded fonts. The watermark layer is an inline base64 PNG, not an external resource. |

## Out of scope

- Attacks that require already-compromised credentials (your GitHub
  token in plain text, your shell, your filesystem).
- Vulnerabilities in transitive dependencies — Cartouche has none at
  runtime (`dependencies = []` in `pyproject.toml`). Dev tools (ruff,
  pytest) are out of scope.
- The hosted dashboard images served via GitHub Camo proxy / raw
  URLs / jsDelivr — these are GitHub / CDN side concerns.

## Versions

Security fixes are applied to the latest `main` and to the latest
released minor version. Older versions may be patched on a
best-effort basis.
