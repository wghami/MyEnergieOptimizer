# 03 — Code quality

The Python version is pinned in `.python-version`. Environment and dependencies are managed with
**uv** only.

## Language conventions

| ID | Rule | Enforced by |
|---|---|---|
| PY-1 | Modern syntax: PEP 695 generics and `type` aliases, `X \| None`, `match`, `Self`, `@override`, `StrEnum`. | ruff `UP`, `FA`; pyright |
| PY-2 | Domain values are immutable: `@dataclass(frozen=True, slots=True, kw_only=True)`. A change returns a new value. | review, architecture tests |
| PY-3 | Validation models (e.g. Pydantic) live only at the boundaries (API, settings, adapter config). They never enter the domain. | import contracts (ARC-1) |
| PY-4 | Every port is a `typing.Protocol`. | review, architecture tests |
| PY-5 | Physical quantities and money carry their unit in the name (`energy_kwh`, `price_eur_per_kwh`) or in a `NewType`. | review |
| PY-6 | Timestamps are timezone-aware; naive `datetime` is forbidden. | ruff `DTZ` |
| PY-7 | No mutable global state, singletons or service locators. Module level only defines things. | ruff `PLW0603`, review |
| PY-8 | Randomness comes only from an injected, seeded generator. | ruff `NPY002`, `S311`, review |
| PY-9 | Each layer has typed exceptions rooted at one project error class. No bare `except`; no catch-all except at the outermost boundary. | ruff `BLE`, `E722`, `TRY` |
| PY-10 | No `print` in library code; logging is structured. A CLI writes to `sys.stdout`/`sys.stderr` explicitly. | ruff `T20` |

## Typing

| ID | Rule | Enforced by |
|---|---|---|
| TYP-1 | pyright **strict** on `src/`, `tests/` and `scripts/`, with zero errors. Lowering the mode per file is forbidden. | `pyright` and `pyright-all` hooks, `standards check-suppressions` |
| TYP-2 | No `Any` in public signatures. | ruff `ANN401` |
| TYP-3 | Each `type: ignore[...]` / `pyright: ignore[...]` names its rule **and** gives a reason: `# pyright: ignore[rule]  # why`. Unnecessary ignores are errors. | `suppressions` hook, pyright `reportUnnecessaryTypeIgnoreComment` |
| TYP-4 | The package ships `py.typed`. | template, review |

## Linting & formatting

| ID | Rule | Enforced by |
|---|---|---|
| LNT-1 | `ruff format` is the only formatter (line length 100). | `ruff-format` hook |
| LNT-2 | `ruff check` uses `select = ["ALL"]`. Each disabled rule is listed in `pyproject.toml` with a reason. | `ruff-check` hook, review of config diffs (CODEOWNERS) |
| LNT-3 | Complexity limits: McCabe ≤ 8, ≤ 6 arguments (use a parameter object instead), ≤ 50 statements. | ruff `C901`, `PLR0913`, `PLR0915` |
| LNT-4 | `noqa` names its codes and gives a reason: `# noqa: E501  # why`. File-level `noqa` is forbidden. | `suppressions` hook |

## Dependency injection

| ID | Rule | Enforced by |
|---|---|---|
| DI-1 | Collaborators are received through `__init__`, typed as ports (Protocols). Nothing constructs its own dependencies. | review, architecture tests |
| DI-2 | Concrete classes are wired in **one** composition root. The container library (if any) is chosen by ADR. | import contracts, review |
| DI-3 | Tests substitute dependencies by overriding providers or passing fakes, never by monkey-patching production code. | review |

## Dependencies

| ID | Rule | Enforced by |
|---|---|---|
| DEP-1 | Every new runtime dependency has an ADR covering why, licence (OSI, MIT-compatible) and maintenance status. | doc-impact rule on `pyproject.toml`, review |
| DEP-2 | Development tools live in dependency groups (`dev`, `docs`), never in runtime dependencies. | review |
| DEP-3 | Dependabot opens weekly update PRs, which pass the same gates as any other PR. | `.github/dependabot.yml` |
