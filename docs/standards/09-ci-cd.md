# 09 — CI/CD (GitHub Actions)

| Workflow | Trigger | Jobs |
|---|---|---|
| `ci.yml` | PR, push to `main` | `pre-commit-stage` · `pre-push-stage` (tests, coverage, docs, contracts, version) · `commits` (every commit, PR title, branch) · `secrets` (gitleaks over the full history) · `audit` (pip-audit) · `release` (on `main`) · `pages` (docs, on `main`) |
| `codeql.yml` | PR, push to `main`, weekly | CodeQL for Python and Actions |
| `nightly.yml` | nightly; PRs labelled `mutation` / `perf` | Mutation score (TST-12), performance budgets (TST-11); a scheduled failure opens a `release-blocker` issue |
| `weekly.yml` | weekly | pip-audit, external links (lychee), template drift (`standards check-template-drift`); a failure opens an issue |

| ID | Rule | Enforced by |
|---|---|---|
| CI-1 | Every `ci.yml` job and CodeQL are **required checks** on `main`, with no bypass, including for admins. | GitHub ruleset |
| CI-2 | CI installs only from the lockfile and fails if it is stale. | `UV_LOCKED=1` |
| CI-3 | The coverage report is uploaded as an artifact; the gate is the absolute 100 % (COV-1), never a delta. | `ci.yml` |
| CI-4 | Releases are automatic: on every green push to `main` the release job tags, builds and publishes ([02](02-commits-and-versioning.md#release-flow-automatic-on-every-merge-to-main)). | `ci.yml` `release` job |
| CI-5 | Jobs declare least-privilege `permissions:`, do not persist credentials, and pin actions by SHA. | `zizmor`, `actionlint` hooks |
| CI-6 | A tag is never deleted or moved. A broken release is fixed forward with a new `fix` commit. | `standards check-version` (a moved tag fails), review |
| CI-7 | While a `release-blocker` issue is open, the release job refuses to release. | `ci.yml` `release` job |
| CI-8 | The Python version comes from `.python-version`; only that version is tested. | `setup-uv` |
| CI-9 | PR CI completes in ≤ 10 minutes; slower suites move to `nightly.yml` with an equivalent gate. | review |
