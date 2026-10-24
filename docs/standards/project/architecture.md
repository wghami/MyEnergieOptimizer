# Architecture — MyEnergieOptimizer

```text
        api ──┐                        ┌── adapters (enedis, csv, nasa-power, pvgis,
              │                        │             open-meteo, storage, jobs)
              ▼                        ▼
         bootstrap (composition root, dishka): the only module that sees everything
              │
      ┌───────┴────────┐
      ▼                ▼
    engine   ⟂     policies          (independent siblings)
      └───────┬────────┘
              ▼
            ports  (Protocols)
              ▼
            domain (pure)
```

The contracts live in `.importlinter` and run in the `import-contracts` hook.

## Layers

| ID | Rule | Enforced by |
|---|---|---|
| MEO-ARC-1 | `domain` and `ports` import only the standard library and numpy: no clingo, dishka, FastAPI, httpx, pandas, Pydantic, SmartMDAO or structlog. | `import-contracts` (contract `pure-domain`) |
| MEO-ARC-2 | Layer order, top to bottom: `bootstrap` → `api` ⟂ `adapters` → `engine` ⟂ `policies` → `ports` → `domain`. ⟂ marks siblings that may not import each other. | `import-contracts` (contract `layers`) |
| MEO-ARC-3 | `engine` and `policies` reach the outside only through ports. They may use SmartMDAO, but never adapters, the API, clingo, dishka, FastAPI, httpx or pandas. | `import-contracts` (contract `core-has-no-io`) |
| MEO-ARC-4 | `adapters` and `api` never import `engine` or `policies` internals; they talk to them through ports and the composition root. | `import-contracts` (contract `edges-stay-apart`) |

## Dependency injection (ADR 0002)

| ID | Rule | Enforced by |
|---|---|---|
| MEO-DI-1 | The container is **dishka**. Providers are declared in `myenergie/bootstrap.py`, grouped by layer. | `import-contracts` (only `bootstrap` sees all layers), review |
| MEO-DI-2 | Scopes: `APP` (settings, registries, profile cache), `REQUEST` (one API call), `SIMULATION` (one run: observer, policy, state, recorder). | review, integration tests |
| MEO-DI-3 | API routes receive services through `dishka.integrations.fastapi` (`FromDishka[...]`). Routers never construct services. | review, API tests |
| MEO-DI-4 | Tests build the container with fake providers (DI-3). | review |

## Plugins

| ID | Rule | Enforced by |
|---|---|---|
| MEO-PLG-1 | Asset kinds, profile and irradiance sources, tariffs, forecasters, policies and observers are registered in typed `Registry[T]`s keyed by `kind`. | review |
| MEO-PLG-2 | Built-ins register through the same `importlib.metadata` entry points as third parties (`myenergie.assets`, `myenergie.profiles`, …); there is no privileged path. | integration test of the registries |
| MEO-PLG-3 | Each adapter's configuration is a Pydantic model with `kind: Literal[...]`, so the API schemas are discriminated unions generated from the registries. | API tests |
| MEO-PLG-4 | Each extension in SPEC §9 (another household, an EV charger, a Tempo tariff, a spot-price forecast, an MPC policy) has an acceptance test that adds it as a test-only plugin, without editing existing modules (PRT-2). | `tests/arch/` |
