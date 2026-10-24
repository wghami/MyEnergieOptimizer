# 0001 — Adopt the python-project-standards template

Status: accepted
Date: 2026-10-24

## Context

Quality rules that live only in people's heads drift. We want them written, versioned and
enforced by tools, and shared across projects.

## Decision

Render this repository from `gh:wghami/python-project-standards` with Copier. The generic
standards in `docs/standards/` and the tooling (hooks, CI, `standards` CLI) come from the template
and are updated with `copier update`. Project rules live in `docs/standards/project/`.

## Consequences

Improvements to the generic rules are made upstream, released, then pulled here. A weekly job
reports when this project is behind (STD-2).

## Alternatives considered

Copying the files by hand: no update path, guaranteed drift.
