# 05 — Testing

**100 % line and branch coverage; nothing less is accepted.** Coverage only proves that every line
ran, not that the tests check it, so mutation testing (TST-12) verifies that the tests detect
deliberate bugs.

## Coverage

| ID | Rule | Enforced by |
|---|---|---|
| COV-1 | `pytest --cov` with `branch = true` and `fail_under = 100` over the package and `scripts/`. | `tests` hook, CI pre-push stage |
| COV-2 | No inline coverage pragma of any kind, anywhere. | `suppressions` hook (`standards check-suppressions`) |
| COV-3 | The only exclusions are the `exclude_also` patterns in `pyproject.toml`: `if TYPE_CHECKING:`, `@overload`, bodies that are only `...`, `assert_never(`. Changing the list needs an ADR. | doc-impact rule on `pyproject.toml`, CODEOWNERS review |
| COV-4 | Coverage is measured on the combined run of every suite except `perf`. | `tests` hook |
| COV-5 | Code that cannot be covered is deleted or redesigned, never excluded. | review |

## Test types

| ID | Suite | Proves | Tools |
|---|---|---|---|
| TST-1 | `tests/unit/` | One unit with fakes for its ports; fast (< 50 ms each) | pytest |
| TST-2 | `tests/integration/` | Real components together, including the composition root | pytest |
| TST-3 | `tests/contract/` | Every implementation of a port satisfies the port's contract; external APIs replayed from recordings | pytest, recorded responses |
| TST-4 | `tests/property/` | Invariants hold for generated inputs | Hypothesis |
| TST-5 | `tests/golden/` | Hand-computed reference cases, each documenting its calculation; exact expected outputs | pytest, syrupy |
| TST-6 | `tests/api/` | Every endpoint: success, validation errors, error bodies (if the project has an API) | httpx, framework test client |
| TST-7 | `tests/api/` (fuzz) | No input generated from the API schema causes a 5xx or a schema-violating response | Schemathesis |
| TST-8 | `tests/security/` | The project's threat model (see [07](07-security.md) and the project rules) | pytest |
| TST-9 | `tests/arch/` | Import contracts, layer purity, extension points, hooks installed (`standards check-hooks-installed`) | import-linter, pytest |
| TST-10 | `docs/`, `README.md` | Every Python code block in the docs runs | pytest-markdown-docs |
| TST-11 | `tests/perf/` (`@pytest.mark.perf`) | Time budgets; run nightly and on PRs labelled `perf` | pytest-benchmark |
| TST-12 | mutation | Mutation score ≥ the threshold set at render time; nightly, and on PRs labelled `mutation`. Mutants that were never evaluated (a failing baseline run) fail too, so `[tool.mutmut] also_copy` lists every file the tests read. A failure opens a release blocker | mutmut, `standards check-mutation-score` |
| TST-13 | `tests/integration/` (e2e) | The deployed shape works end to end (boot, request, result) | pytest |

A suite only exists once there is something for it to test. The template creates `unit/` and
`arch/`; the others appear with the first code that needs them.

## Writing tests

| ID | Rule | Enforced by |
|---|---|---|
| TW-1 | A bug fix starts with a test that reproduces the bug. | review |
| TW-2 | Test names state the behaviour: `test_surplus_is_sold_when_export_price_is_high`. | ruff `PT`, review |
| TW-3 | Tests never use the network (except recording contract cassettes on purpose). | `pytest-socket` (`--disable-socket`) |
| TW-4 | Tests are independent of order. | `pytest-randomly` |
| TW-5 | No sleeping; time is injected. | ruff banned API `time.sleep` |
| TW-6 | Test data is small and committed under `tests/fixtures/` (LAY-4). | `check-added-large-files` |
| TW-7 | A flaky test is fixed or deleted within one working day. Automatic reruns are not allowed. | review |
| TW-8 | Warnings are errors. | pytest `filterwarnings = ["error"]` |
