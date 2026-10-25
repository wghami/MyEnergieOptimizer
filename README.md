# MyEnergieOptimizer

<!-- standards:badges:start -->
[![CI](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/ci.yml) [![CodeQL](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/codeql.yml) [![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/wghami/MyEnergieOptimizer/badge)](https://scorecard.dev/viewer/?uri=github.com/wghami/MyEnergieOptimizer) [![Nightly](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/nightly.yml/badge.svg?event=schedule)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/nightly.yml) [![docs](https://img.shields.io/website?url=https%3A%2F%2Fwghami.github.io%2FMyEnergieOptimizer%2F&label=docs)](https://wghami.github.io/MyEnergieOptimizer/)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwghami%2FMyEnergieOptimizer%2Fbadges%2Fcoverage.json)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/ci.yml) [![mutation](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwghami%2FMyEnergieOptimizer%2Fbadges%2Fmutation.json)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/nightly.yml) [![docstrings](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwghami%2FMyEnergieOptimizer%2Fbadges%2Fdocstrings.json)](https://github.com/wghami/MyEnergieOptimizer/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/wghami/MyEnergieOptimizer?sort=semver)](https://github.com/wghami/MyEnergieOptimizer/releases) [![python](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwghami%2FMyEnergieOptimizer%2Fmain%2Fpyproject.toml&query=%24.project%5B%27requires-python%27%5D&label=python&logo=python&logoColor=white)](pyproject.toml) [![license](https://img.shields.io/github/license/wghami/MyEnergieOptimizer)](LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![types: pyright strict](https://img.shields.io/badge/types-pyright%20strict-2a6db2)](docs/standards/03-code-quality.md) [![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](.pre-commit-config.yaml) [![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-fe5196?logo=conventionalcommits&logoColor=white)](https://www.conventionalcommits.org) [![standards](https://img.shields.io/badge/dynamic/yaml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fwghami%2FMyEnergieOptimizer%2Fmain%2F.copier-answers.yml&query=%24._commit&label=standards&color=6f42c1)](https://github.com/wghami/python-project-standards) [![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)
<!-- standards:badges:end -->

Simulate a home, and later an energy community, whose electricity dispatch is decided by
**logic rules the user writes**: who gets the solar energy first, when the battery charges, and
whether surplus is sold or stored. The rules run as [SmartMDAO](https://github.com/wghami/SmartMDAO)
rule disciplines, are verified before a run, and never see the future except through an explicit
forecast.

- Specification: [`planning/SPEC.md`](planning/SPEC.md) · Roadmap: [`planning/ROADMAP.md`](planning/ROADMAP.md)
- Engineering standards (binding): [`docs/standards/`](docs/standards/README.md)

## Shift left, by design

Every rule in the [engineering standards](docs/standards/README.md) is enforced by a gate, and
every gate runs **as early as it can**: on your machine before the code leaves it, then again in
CI, and the slow or external checks on a schedule. This table is generated from the hook and
workflow configuration, so it cannot drift from what actually runs.

<!-- standards:gates:start -->
**34 gates.** 22 run on your machine before code leaves it (`pre-commit` / `pre-push` hooks); CI reruns every one of them, and scheduled jobs add the slow and the external checks.

| Gate | 💻 commit | 💻 push | ☁️ CI | 🌙 nightly | 📅 weekly |
|---|:-:|:-:|:-:|:-:|:-:|
| pre-commit-hooks: `check-added-large-files` · `check-case-conflict` · `check-merge-conflict` · `check-toml` · `check-yaml` · `detect-private-key` · `end-of-file-fixer` · `trailing-whitespace` | ✓ |  | ✓ |  |  |
| gitleaks (`gitleaks`) | ✓ |  | ✓ |  |  |
| ruff format (`ruff-format`) | ✓ |  | ✓ |  |  |
| ruff check (`ruff-check`) | ✓ |  | ✓ |  |  |
| pyright (changed files) (`pyright`) | ✓ |  | ✓ |  |  |
| no silent suppressions (`suppressions`) | ✓ |  | ✓ |  |  |
| uv.lock in sync (`uv-lock`) | ✓ |  | ✓ |  |  |
| actionlint (`actionlint`) | ✓ |  | ✓ |  |  |
| zizmor (workflow security) (`zizmor`) | ✓ |  | ✓ |  |  |
| conventional commit message (`commit-msg`) | ✓ |  | ✓ |  |  |
| branch name (`branch-name`) |  | ✓ | ✓ |  |  |
| pyright (whole repository) (`pyright-all`) |  | ✓ | ✓ |  |  |
| import contracts (`import-contracts`) |  | ✓ | ✓ |  |  |
| tests (100 % line + branch coverage) (`tests`) |  | ✓ | ✓ |  |  |
| docstring coverage 100 % (`docstrings`) |  | ✓ | ✓ |  |  |
| bandit (`bandit`) |  | ✓ | ✓ |  |  |
| docs build (strict) (`docs-build`) |  | ✓ | ✓ |  |  |
| docs changed with what they describe (`doc-impact`) |  | ✓ | ✓ |  |  |
| version from tags, tags published (`version-tag`) |  | ✓ | ✓ |  |  |
| standards consistent with tooling (`standards-docs`) |  | ✓ | ✓ |  |  |
| README badges and gates table up to date (`readme`) |  | ✓ | ✓ |  |  |
| every hook stage runs in CI (`hook-parity`) |  | ✓ | ✓ |  |  |
| commits, PR title, branch name |  |  | ✓ |  |  |
| secret scan (full history) |  |  | ✓ |  |  |
| dependency audit |  |  | ✓ |  |  |
| publish and verify docs |  |  | ✓ |  |  |
| CodeQL (Python, Actions) |  |  | ✓ |  | ✓ |
| mutation score ≥ 90 % |  |  | 🏷️ | ✓ |  |
| performance budgets |  |  | 🏷️ | ✓ |  |
| OpenSSF Scorecard |  |  | ✓ |  | ✓ |
| audit |  |  |  |  | ✓ |
| links |  |  |  |  | ✓ |
| drift |  |  |  |  | ✓ |
| deployed docs still served |  |  |  |  | ✓ |
<!-- standards:gates:end -->

## Development

```bash
uv sync
uv run pre-commit install
uv run pytest
```
