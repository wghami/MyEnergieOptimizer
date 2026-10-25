# Agent instructions

The engineering standards in `docs/standards/` are **binding**. Read `docs/standards/README.md`
before changing anything; satisfy `docs/standards/10-definition-of-done.md` before calling work done.
Project-specific rules live in `docs/standards/project/` and extend (never weaken) the generic ones.

- Scope and design: `planning/SPEC.md`. Decisions: `planning/adr/`.
- Environment: `uv` only (`uv sync`, `uv run …`). Hooks: `uv run pre-commit install`.
- Commits: Conventional Commits with the scopes in `standards.toml`. Never write a version by hand.
- Coverage: 100 % line + branch. Never add `pragma: no cover`; never add a reasonless `noqa`/ignore.
- Generic standards come from the `python-project-standards` template: improve them **there**
  (see `docs/standards/11-keeping-standards-current.md`), then `copier update` here.

## Feedback on the standards (STD-7)

Whenever a generic rule is unclear, wrong, too costly, produces a false positive, or is missing,
**do not work around it**. Append an entry to `planning/standards-feedback.md` (format in the
file): the rule, the context, the problem and a proposal. Mention it to the user, who files it
upstream as a "Standards feedback" issue on `wghami/python-project-standards`. Record the issue
URL in the entry. A fix arrives through a template release and `copier update`.
