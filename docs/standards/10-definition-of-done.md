# 10 — Definition of Done

A change is **done** only when all of the following are true. The PR template repeats this list.
🤖 = checked by CI.

## Code

- [ ] 🤖 Lint, format, strict types and import contracts are green.
- [ ] The design follows [04](04-architecture.md): ports, injection through the composition root,
      no new coupling.
- [ ] A new port or extension point has a contract test and an extension test (PRT-1, PRT-2).

## Tests

- [ ] 🤖 Line and branch coverage is 100 %, with no inline exclusions.
- [ ] A bug fix comes with a test that failed before the fix.
- [ ] A behaviour change updates or adds a golden case, or the PR explains why none applies.
- [ ] A new invariant has a property test; a new input surface has security tests.

## Documentation

- [ ] 🤖 Docstrings at 100 %, doc examples executed, strict docs build, doc impact satisfied.
- [ ] A non-obvious decision has an ADR.
- [ ] `planning/ROADMAP.md` is updated if a milestone task was completed.

## History & release

- [ ] 🤖 Every commit and the PR title are Conventional Commits; the branch name is valid.
- [ ] 🤖 No hand-written version; the tag check is green.
- [ ] Breaking changes are marked (`!` + `BREAKING CHANGE:`) and explained.

## Security

- [ ] 🤖 Secret scan, dependency audit, bandit and CodeQL are clean.
- [ ] No new dependency without an ADR (DEP-1).
