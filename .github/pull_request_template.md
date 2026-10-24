<!-- The PR title becomes the squash commit: it must be a Conventional Commit (COM-4). -->

## What and why

## Definition of Done (docs/standards/10-definition-of-done.md)

🤖 = enforced by CI. Tick the others; the reviewer verifies them.

- [ ] Design follows 04-architecture; no new coupling; dependencies injected through the composition root
- [ ] A bug fix has a test that failed before the fix
- [ ] Behaviour change → golden scenario updated or added (or explained below)
- [ ] New invariant → property test; new input surface → security test
- [ ] Non-obvious decision → ADR in `planning/adr/`
- [ ] `planning/ROADMAP.md` updated if a milestone task is complete
- [ ] Breaking change marked with `!` + `BREAKING CHANGE:` footer
- [ ] No new dependency without an ADR (DEP-1)
- 🤖 lint · types · import contracts · tests with 100 % coverage · docstrings · docs build · doc impact · commits · version/tag · secrets · audit · CodeQL
