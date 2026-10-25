# 01 — Repository layout

```text
<project>/
├── planning/                 # what we build and why
│   ├── SPEC.md               # the specification (source of truth for scope)
│   ├── ROADMAP.md            # milestones and their status
│   ├── milestones/           # one file per milestone: goals, tasks, acceptance criteria
│   ├── adr/                  # Architecture Decision Records: NNNN-title.md
│   └── standards-feedback.md # friction with the generic standards, to file upstream (STD-7)
├── docs/                     # published documentation (mkdocs-material)
│   ├── standards/            # these binding rules (from the template)
│   │   └── project/          # project rules (owned by the project; linked from its README, not the nav)
│   ├── reference.md          # API reference, generated from docstrings at build time
│   └── …                     # guides, architecture
├── src/<package>/            # the package
├── tests/                    # unit/ integration/ contract/ property/ golden/ api/ security/ perf/ arch/
├── scripts/                  # repository tooling used by hooks and CI (typed, tested)
├── .github/                  # workflows, scripts/ for them, PR template, CODEOWNERS, dependabot.yml
├── standards.toml            # configuration of the `standards` checks
├── .copier-answers.yml       # which template release this project was rendered from
├── AGENTS.md, CLAUDE.md      # point AI agents to these standards
├── LICENSE, SECURITY.md, README.md
└── pyproject.toml, uv.lock, .python-version, .pre-commit-config.yaml, .importlinter, mkdocs.yml
```

| ID | Rule | Enforced by |
|---|---|---|
| LAY-1 | Production code lives only in `src/<package>/`. | packaging config, review |
| LAY-2 | Tests are grouped by kind of test (see [05](05-testing.md)). Each test module states what it proves in its docstring. | ruff `D100`, review |
| LAY-3 | Generated material (API reference, OpenAPI files, release notes) is never edited by hand. | generated at build time, drift checks |
| LAY-4 | Committed files are ≤ 1 MB. Larger datasets are fetched or configured by path. | `check-added-large-files` |
| LAY-5 | `scripts/` contains only code that hooks or CI call. It is typed and covered like production code. | coverage `source`, pyright `include` |
| LAY-6 | Every non-obvious design choice has an ADR in `planning/adr/` (template `0000-template.md`). | review (PR checklist) |
| LAY-7 | `uv.lock` is committed and always in sync with `pyproject.toml`. | `uv-lock` hook, `UV_LOCKED` in CI |
