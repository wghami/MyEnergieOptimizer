# 06 — Documentation

Docs go stale in three ways: text that describes code that has since changed, generated material
that was not regenerated, and examples that no longer run. Each has a mechanical guard.

| Where | Content | Written by |
|---|---|---|
| `README.md` | Pitch, install, first example | hand (examples executed) |
| `docs/` | Guides and architecture | hand (examples executed) |
| `docs/reference.md` | Python API | **generated** at build time (mkdocstrings) |
| `docs/standards/` | These rules | the template; project rules in `project/` |
| `planning/` | Spec, roadmap, milestones, ADRs | hand |
| GitHub Releases | Release notes | **generated** (commitizen) |

| ID | Rule | Enforced by |
|---|---|---|
| DOC-1 | Every public module, class, function and method has a Google-style docstring stating units and raised exceptions. | `docstrings` hook (interrogate 100 %), ruff `D` |
| DOC-2 | Every Python code block in Markdown runs and is executed. A block that is only illustrative is fenced as `text`. | `tests` hook (pytest-markdown-docs) |
| DOC-3 | Generated documentation (API reference, schemas) is produced by the build or checked for drift, never maintained by hand. | `docs-build` hook, project drift checks |
| DOC-4 | The docs site builds with zero warnings, and internal links and anchors resolve. External links are checked weekly. | `docs-build` hook (`mkdocs build --strict`), weekly lychee |
| DOC-5 | **Doc impact:** every watched path in `standards.toml` is mapped to the docs that describe it. A change without its docs fails, unless a commit carries `Docs-Reviewed: <why>`. Unmapped watched paths fail too, so the map stays complete. | `doc-impact` hook (`standards check-doc-impact`) |
| DOC-6 | The standards documents are consistent with the tooling: unique rule IDs, every cell filled, every hook and every `standards` command documented, nothing cited that does not exist. | `standards-docs` hook (`standards check-standards`) |
| DOC-7 | `planning/ROADMAP.md` is updated in the PR that completes a milestone task. | PR checklist |
| DOC-8 | An accepted ADR is never edited; it is superseded by a new ADR that links back. | review |
| DOC-9 | Docs are written for a reader who has not seen the code: units, assumptions and *why*. | review |
| DOC-11 | Documentation is deployed to GitHub Pages automatically on every green push to `main`, then **verified where it is served**: every page of the sitemap answers 200 and the served `build.json` names the commit just built. The live site is re-verified weekly. | `ci.yml` `pages` job and weekly `site` job (`standards check-site`) |
| DOC-10 | The README starts with the badges and shows the shift-left gates table. Both are **generated** between `<!-- standards:… -->` markers from the workflows, the hooks and `.copier-answers.yml`, and the push fails when they were stale (the hook rewrites them, like a formatter). Every badge is backed by a gate: status badges by workflows, measured badges by the gates' own reports (CI-10). | `readme` hook (`standards readme`) |
