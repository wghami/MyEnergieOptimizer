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

## 2026-10-25 — DOC-10: the README task aborts `copier update` on existing projects

- **Context:** updating this project from v0.2.x to v0.3.1.
- **Problem:** the new post-render task `standards readme --write` fails when README.md has no
  marker blocks yet, which is the case for every project rendered before DOC-10. The README is
  project-owned, so the update cannot add the markers itself.
- **Proposal:** the task should not fail the update. It should tell the user to add the markers,
  and the `readme` hook keeps enforcing DOC-10 on the next push.
- **Status:** filed https://github.com/wghami/python-project-standards/issues/7, resolved in v0.3.2
