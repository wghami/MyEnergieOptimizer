# Standards feedback

Friction with the generic standards, recorded while working on this project (STD-7). Each entry
becomes an issue on the template repository; never weaken a rule locally instead.

<!-- Copy this block for each entry, newest first.

## YYYY-MM-DD — <rule ID or "missing rule">: <one-line summary>

- **Context:** what we were doing when the rule got in the way, or was missing.
- **Problem:** what is wrong: unclear, too strict, too weak, wrong tool, false positive, cost.
- **Proposal:** the change to the document and/or its enforcement.
- **Status:** open | filed <issue URL> | resolved in vX.Y.Z

-->

## 2026-10-25 — missing rule: a git-ignored place for personal data

- **Context:** the user provided a real electricity bill as a test reference; it must never reach
  GitHub.
- **Problem:** the template has no convention for personal or confidential inputs; each project
  would improvise, and a slip publishes personal data.
- **Proposal:** the template's `.gitignore` ignores `private/`; a rule (e.g. SEC-14) says personal
  data lives only there; tests that need it are skipped when it is absent, and CI uses synthetic
  equivalents with the same structure.
- **Status:** open (applied locally in `.gitignore` meanwhile)

## 2026-10-25 — COM-4: a breaking PR title can never pass `check-pr-title`

- **Context:** the PR renaming the project, titled `build(release)!: …`.
- **Problem:** the title was held to COM-2's footer rule, but a title has no body; the footer
  reaches `main` through the squash body (BR-4) and is already checked on each commit.
- **Proposal:** check PR titles as headers only.
- **Status:** filed https://github.com/wghami/python-project-standards/issues/11, resolved in v0.3.4

## 2026-10-25 — DOC-4, TST-11, TST-12, CI-7: five gate holes found rolling out v0.3.1

- **Context:** first main-branch run after updating to v0.3.2; the docs job, the release job and
  the nightly job failed, while the local hooks had passed.
- **Problem:** (1) `mkdocs build --strict --quiet` lets warnings through, so the local docs gate
  was blind; (2) project pages had to be listed in the template-owned `mkdocs.yml` nav, which the
  update replaced; (3) zero mutants (no functions yet) failed the nightly job like a crash;
  (4) the perf job hit a pytest usage error; (5) an open release blocker turned `main` red on a
  push that released nothing.
- **Proposal:** fix all five upstream, each with a test or smoke check.
- **Status:** filed https://github.com/wghami/python-project-standards/issues/9, resolved in v0.3.3

## 2026-10-25 — DOC-10: the README task aborts `copier update` on existing projects

- **Context:** updating this project from v0.2.x to v0.3.1.
- **Problem:** the new post-render task `standards readme --write` fails when README.md has no
  marker blocks yet, which is the case for every project rendered before DOC-10. The README is
  project-owned, so the update cannot add the markers itself.
- **Proposal:** the task should not fail the update. It should tell the user to add the markers,
  and the `readme` hook keeps enforcing DOC-10 on the next push.
- **Status:** filed https://github.com/wghami/python-project-standards/issues/7, resolved in v0.3.2
