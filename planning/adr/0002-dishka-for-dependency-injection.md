# 0002 — dishka for dependency injection

Status: accepted
Date: 2026-10-24

## Context

The design is ports and adapters, with many swappable implementations (profile sources, weather
APIs, forecasters, policies, storage, job runners) and three natural lifetimes: the application,
one API request, and one simulation run. Wiring this by hand in a single composition root works,
but scopes and their finalisation become boilerplate quickly.

## Decision

Use **dishka** as the container, wired only in `myenergy/bootstrap.py` (MEO-DI-1…4), with the
scopes `APP`, `REQUEST` and `SIMULATION`. Its FastAPI integration injects services into routes.

## Consequences

- Only `bootstrap` (and the dishka FastAPI integration in `api`) depends on dishka; the domain,
  ports, engine and policies stay framework-free (import contracts).
- Tests override providers instead of monkey-patching.
- Harder: the container is one more library to learn. Mistakes in scope declarations surface at
  container build time, which an integration test covers.

## Alternatives considered

- Plain constructor injection with a hand-written root: no dependency, but scope lifetimes and
  cleanup would be re-implemented by hand.
- `dependency-injector`: mature, but its declarative containers and Cython build are heavier, and
  it is less idiomatic with modern typing.
