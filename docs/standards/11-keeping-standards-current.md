# 11 — Keeping the standards current

The generic standards and their tooling come from one template repository,
[`wghami/python-project-standards`](https://github.com/wghami/python-project-standards), which
contains:

- the Copier template: these documents, the hooks, the CI workflows and the tool configuration;
- the `standards` CLI that hooks and CI call.

Projects are **rendered** from a tagged release of the template and **updated** from later
releases.

```bash
uvx copier copy --trust gh:wghami/python-project-standards my-project   # new project
uvx copier update --trust                                               # inside a project
```

| ID | Rule | Enforced by |
|---|---|---|
| STD-1 | Generic rules (everything in `docs/standards/` except `project/`) are changed **only in the template repository**, by PR, and released with a tag. Projects never edit them locally. | `copier update` shows local edits as conflicts; CODEOWNERS review |
| STD-2 | Every project runs on the latest template release. A newer release is reported weekly and pulled with `copier update` in a `build(standards):` PR. | weekly `standards check-template-drift` |
| STD-3 | The documents and the tooling never disagree: rule IDs are unique and complete, every hook and every CLI command is documented, nothing cited is missing. | `standards-docs` hook (`standards check-standards`), in the template's own CI and in every project |
| STD-4 | A change to tooling configuration (hooks, workflows, `pyproject.toml`, `standards.toml`, `.importlinter`, `mkdocs.yml`) comes with a change to the standard that describes it. | `doc-impact` hook (DOC-5) |
| STD-5 | Project-specific rules live in `docs/standards/project/`. They may add rules but never weaken a generic one; use a project prefix for their IDs. | review, `standards check-standards` (unique IDs) |
| STD-6 | When a project discovers a rule that would help every project, it is proposed upstream rather than kept local. | review |
| STD-7 | Friction with a generic rule (unclear, wrong, too costly, false positive, or a missing rule) is recorded in `planning/standards-feedback.md`, never worked around. AI agents do this too (`AGENTS.md`). Each entry becomes a "Standards feedback" issue on the template repository, and its URL is recorded in the entry. | `AGENTS.md`, issue form on the template repository, review |

## Changing a standard

0. Most changes start as an entry in a project's `planning/standards-feedback.md` (STD-7), then
   an issue on the template repository.
1. Open a PR on the template repository. It changes the document **and** the tooling in the same
   PR, and its CI renders a sample project and runs the full pipeline on it.
2. Merging releases a new template version automatically.
3. Each project's weekly drift check opens an issue. Run `uvx copier update --trust`, resolve any
   conflicts, and merge the `build(standards): update to vX.Y.Z` PR.
