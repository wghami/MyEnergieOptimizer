# 07 — Security

Generic rules. Each project adds its own threat model to `docs/standards/project/`, with tests in
`tests/security/`.

## Application

| ID | Rule | Enforced by |
|---|---|---|
| SEC-1 | Every external input has explicit size and range limits, validated at the boundary. | review, `tests/security/` |
| SEC-2 | User input never becomes a file path, URL, shell command, query or code without an allow-list. Resolved paths are checked against their root. | ruff `S` (bandit rules), `bandit` hook, `tests/security/` |
| SEC-3 | Error responses never contain stack traces, file paths or internal identifiers; a correlation ID links them to the logs. | `tests/security/` |
| SEC-4 | No unsafe deserialisation (`pickle`, `marshal`, `yaml.load`, `eval`, `exec`). | ruff banned API, `bandit` hook |
| SEC-5 | Long or untrusted computations run with a time limit and a memory limit. | review, `tests/security/` |
| SEC-6 | Exported CSV/spreadsheet cells are escaped against formula injection. | `tests/security/` |

## Supply chain & repository

| ID | Rule | Enforced by |
|---|---|---|
| SEC-7 | No secrets in the repository. Configuration comes from the environment; `.env` is ignored. | `gitleaks` hook, CI full-history scan, GitHub push protection |
| SEC-8 | Dependencies have no known vulnerabilities. | CI and weekly `pip-audit`, Dependabot security updates |
| SEC-9 | Static analysis passes. | CodeQL (Python and Actions), `bandit` hook |
| SEC-10 | Releases ship an SBOM and build provenance. | release job (VER-5) |
| SEC-11 | GitHub Actions are pinned by commit SHA, with least-privilege `permissions:` per job and no persisted credentials. | `zizmor` and `actionlint` hooks |
| SEC-12 | Vulnerabilities are reported privately (`SECURITY.md`). | repository file |
