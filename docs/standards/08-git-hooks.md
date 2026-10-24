# 08 — Git hooks

Managed by **pre-commit** (`.pre-commit-config.yaml`). Install once per clone:

```bash
uv sync
uv run pre-commit install
```

| ID | Rule | Enforced by |
|---|---|---|
| HK-1 | Hooks are installed for the `pre-commit`, `commit-msg` and `pre-push` stages. | `tests/arch` (`standards check-hooks-installed`, skipped in CI) |
| HK-2 | CI reruns every stage, so `--no-verify` saves nothing. | CI |
| HK-3 | Hooks run tools through `uv run --frozen`, i.e. the locked versions. | review of `.pre-commit-config.yaml` |
| HK-4 | The pre-commit stage stays fast (≈ 10 s); anything slower belongs in pre-push. | review |
| HK-5 | Every stage used locally has a matching CI step. | `hook-parity` hook (`standards check-hook-parity`) |

## pre-commit stage (staged files)

| Hook | Checks |
|---|---|
| `ruff-format`, `ruff-check` | Formatting and lint (LNT-1, LNT-2) |
| `pyright` | Strict types on the changed files (TYP-1) |
| `suppressions` | No coverage pragmas, no `nosec`, no reasonless `noqa` / ignores (COV-2, TYP-3, LNT-4) |
| `uv-lock` | `uv.lock` matches `pyproject.toml` (LAY-7) |
| `actionlint`, `zizmor` | Workflow correctness and security (SEC-11) |
| `gitleaks`, `detect-private-key` | No secrets (SEC-7) |
| `check-added-large-files`, `check-case-conflict`, `check-merge-conflict`, `check-toml`, `check-yaml`, `end-of-file-fixer`, `trailing-whitespace` | File hygiene (LAY-4) |

## commit-msg stage

| Hook | Checks |
|---|---|
| `commit-msg` | Conventional Commit (COM-1, COM-2) |

## pre-push stage (whole repository)

| Hook | Checks |
|---|---|
| `branch-name` | `<type>/<topic>` (BR-1) |
| `pyright-all` | Strict types everywhere (TYP-1) |
| `import-contracts` | Architecture (ARC-1…6) |
| `tests` | All suites except `perf`, 100 % line and branch coverage (COV-1) |
| `docstrings` | 100 % docstring coverage of the public API (DOC-1) |
| `bandit` | Security lint at medium severity and above; low-severity patterns are already ruff `S` rules with reasoned `noqa` (SEC-4, SEC-9) |
| `docs-build` | Strict docs build (DOC-4) |
| `doc-impact` | Docs changed together with what they describe (DOC-5); compares with `STANDARDS_BASE_REF` or `origin/main` |
| `version-tag` | Version from tags; latest tag published (VER-1, VER-3) |
| `standards-docs` | Standards consistent with the tooling (DOC-6) |
| `hook-parity` | CI reruns every stage (HK-5) |
