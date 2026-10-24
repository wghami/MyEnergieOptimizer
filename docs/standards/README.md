# Engineering Standards

These documents are **binding**. Every contributor, human or AI agent, follows them. A change that
breaks a rule is not merged.

Each rule has an ID (e.g. `TST-3`) so reviews and commit messages can cite it. Each rule also names
**what enforces it**. A rule that only a human enforces is marked `review` and is listed in the
pull-request checklist.

| # | Document | Covers |
|---|---|---|
| 01 | [Repository layout](01-repository-layout.md) | Where things live |
| 02 | [Commits, branches & versioning](02-commits-and-versioning.md) | Conventional Commits, SemVer, tags, releases |
| 03 | [Code quality](03-code-quality.md) | Python conventions, typing, linting, DI |
| 04 | [Architecture rules](04-architecture.md) | Layers, ports & adapters, plugins, import contracts |
| 05 | [Testing](05-testing.md) | Test types, 100 % coverage, mutation testing |
| 06 | [Documentation](06-documentation.md) | Keeping docs from going stale, docstrings, ADRs |
| 07 | [Security](07-security.md) | Threats specific to this app and their mitigations |
| 08 | [Git hooks](08-git-hooks.md) | What runs at commit, commit-msg and pre-push |
| 09 | [CI/CD](09-ci-cd.md) | Workflows, required checks, automatic releases |
| 10 | [Definition of Done](10-definition-of-done.md) | The checklist every change must satisfy |

## Principles

1. **Machines enforce, humans judge.** Anything a tool can check is checked by a tool, locally
   *and* in CI.
2. **Local hooks are a convenience; CI is the authority.** Hooks can be skipped with
   `--no-verify`. CI cannot. Every hook is repeated in CI.
3. **No silent exceptions.** Exclusions (coverage, lint, typing) are declared in configuration,
   with a reason, where review can see them, and never inline.
4. **Changing a standard is a change like any other.** It goes through a PR with an ADR in
   `planning/adr/`, and the doc-impact rule ([DOC-6](06-documentation.md)) applies.

## Status

Agreed on 2026-10-24. The tooling that enforces these rules is delivered in milestone **M0**
(`planning/SPEC.md` §10). Until M0 is merged, the rules apply through review.
