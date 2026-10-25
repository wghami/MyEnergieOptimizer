# MyEnergyOptimizer — Specification (v1.0)

> Status: **agreed** (decisions in §12). Delivery is tracked in `ROADMAP.md`; the binding engineering
> rules are in `docs/standards/` (generic, from the template) and `docs/standards/project/`.

## 1. Purpose

An API that simulates an energy system over a period of time. The first target is **a single home**;
later it should handle an **energy community**. A dispatch policy decides at each step who receives
the solar energy, what the battery does, and whether surplus is sold or stored. **Users define that
policy as logic rules**, and the rules are executed through **SmartMDAO** (`RuleDiscipline` + `Bands`).

Guiding principles:

1. **Causality.** The controller never sees the future. The only knowledge it has about what comes
   next is an explicit `Forecast`, which can be wrong. The code structure enforces this; it is not
   left to convention.
2. **Topology from day one.** One home is a community with one site. Adding households means
   changing configuration, not code.
3. **Ports & adapters + dependency injection.** The domain imports nothing from FastAPI, pandas
   I/O, clingo or SmartMDAO. Every external concern sits behind a `Protocol`.
4. **Open for extension, closed for modification.** New asset kinds, profile sources, tariffs,
   forecasters and policies are plugins added to a registry. Existing code is never edited to add one.
5. **Checked before it runs** (the SmartMDAO ethos). Before any simulation, a policy is validated
   exhaustively over its finite set of facts.

## 2. Scope

| In v1 | Later |
|---|---|
| 1 site: N consumers, N PV arrays, 0..N batteries, 1 grid connection | Several sites, shared assets, allocation keys (energy community) |
| Fixed load and PV curves (Enedis, CSV, synthetic) | Flexible / shiftable loads |
| Time-varying import and export prices | Tempo / spot-price adapters |
| Unlimited grid import and export | Grid caps (feed-in limit) |
| Step-by-step rule policy, no forecast | Forecast-aware rules, MPC (re-plan each step), scenario campaigns |
| REST API, synchronous runs + background jobs | GUI, persistent DB, auth |

## 3. Domain model (`domain/`, pure Python, no I/O)

All types are immutable: `@dataclass(frozen=True, slots=True)`. Energy is in **kWh per step**,
power in **kW**, money in **EUR**. NewTypes or units keep these from being mixed up.

- **`TimeGrid`**: `start`, `end`, `dt` (a `timedelta` that divides the period evenly), `tz`
  (default `Europe/Paris`). Timestamps are stored in UTC and are aware of daylight saving time. It
  provides the step index ↔ timestamp mapping.
- **`TimeSeries`**: values aligned on a `TimeGrid` and backed by a numpy array, with a `kind`
  (energy or power, which decides how resampling works). It is immutable.
- **Assets** (`Asset` protocol: `id`, `kind`, `site_id`):
  - `Consumer(id, load: ProfileRef, priority_class?)`
  - `PVArray(id, production: ProfileRef)`
  - `Battery(id, capacity_kwh, p_charge_max_kw, p_discharge_max_kw, eta_charge, eta_discharge, soc_min, soc_max, soc_initial)`
  - `GridConnection(id, import_tariff: Tariff, export_tariff: Tariff)`
- **`Site`**: a group of assets behind one meter. **`Topology`**: sites plus (later) shared assets
  and an allocation key. v1 = `Topology(sites=[one_site])`.
- **`Tariff`** protocol: `price(step) -> EUR/kWh`. Implementations: `FlatTariff`,
  `TimeOfUseTariff` (weekday/hour schedule, e.g. HP/HC), `SeriesTariff` (any `TimeSeries`).
- **`SystemState`**: the state of each battery (SoC) plus anything a policy remembers. It moves
  forward only through `state.advance(flows)`.
- **`Decision`**: the *policy* for one step, not kWh setpoints (see §5). It contains:
  - `priority: tuple[ConsumerId, ...]`
  - `battery_mode: Mapping[BatteryId, charge|discharge|idle]`
  - `surplus: sell|store`
  - `grid_charging: bool`
  - `rationale: frozenset[str]` (the atoms that justified it)
- **`Flows`**: an energy-flow graph for one step. Edges are `(source, sink) -> kWh` over the nodes
  `{pv_*, battery_*, consumer_*, grid}`. Because it is generic, community sharing becomes just more
  edges.
- **KPIs**: total import cost, export revenue, net bill, self-consumption rate, self-sufficiency
  (autarky) rate, battery equivalent full cycles, energy sold and bought.

**Invariants**, enforced by property tests with Hypothesis on every step:
- Energy balance per node, losses included.
- `soc_min ≤ SoC ≤ soc_max`.
- No flow is negative.
- No simultaneous import and export at the same meter.
- Battery power limits are respected.

## 4. Simulation engine (`engine/`)

```
for step in grid:
    obs      = observer.observe(step)            # measurements up to step - lag only
    forecast = forecaster.forecast(obs, horizon) # explicit, possibly wrong
    decision = policy.decide(obs, forecast, state)
    realized = world.realize(step)               # actual load and PV during the step
    flows    = physics.settle(decision, realized, state)   # SmartMDAO step pipeline
    state    = state.advance(flows)
    for hook in hooks: hook.on_step(step, obs, decision, flows, state)
```

- **Information boundary.** `World` owns the full series. `Observer` only exposes a `HistoryView`
  that cannot be indexed beyond `step - information_lag`. The default lag is 1 (realistic: you know
  the last metered interval); 0 means an ideal sensor. A dedicated test checks that no policy or
  forecaster can read future data.
- **Why a `Decision` is a policy, not setpoints.** The decision is taken *before* the step's real
  values are known. `physics.settle` applies the priorities and modes to the *realized* values, so
  a wrong expectation can never violate energy balance. It only costs money, which is the effect we
  want to measure.
- **Per-step SmartMDAO pipeline**, built once by a `StepPipelineFactory` from the `Topology`:
  `Bands` (discretise) → `RuleDiscipline` (decide) → `allocate_pv` → `dispatch_battery` →
  `settle_grid` → `price_flows`.
  - `analyze()` and `validate()` run on it at build time.
  - For a community, the factory adds a `share_within_community` step. No other step changes.
- **Hooks** (observer pattern): `Recorder` (writes the result frame), `ProgressReporter` (for jobs),
  `DecisionTracer`.

## 5. Policies (`policies/`) — the `DispatchPolicy` port

```python
class DispatchPolicy(Protocol):
    def decide(self, obs: Observation, forecast: Forecast, state: SystemState) -> Decision: ...
```

| Policy | Purpose | Milestone |
|---|---|---|
| `GreedySelfConsumption` | Baseline; reference for tests | M2 |
| `RulePolicy` | User logic → ASP → SmartMDAO `RuleDiscipline` | M3 |
| `ForecastRulePolicy` | Same rules, plus facts derived from the forecast (`forecast_surplus_band`, `price_trend`) | M5 |
| `RecedingHorizonPolicy` (MPC) | Optimizes over the forecast horizon, applies step 1, re-plans next step: "optimize according to what we expect, correct as we go" | M6 |
| `OraclePolicy` | Perfect foresight; a benchmark for how far a policy is from the best possible result | M6 |

### 5.1 Rules in detail

**Facts** are produced by declared `Bands`, which can be edited and are visible in `explain()`:
- `price_import_band`, `price_export_band` (e.g. `low/mid/high`; thresholds set by the user)
- `soc_band(B)` (`empty/low/mid/high/full`)
- `surplus_band` (expected PV minus load: `deficit/none/small/large`)
- `period` (`HP/HC`, weekday or weekend)
- consumer classes

Floats never reach ASP; SmartMDAO refuses them anyway.

**Decision vocabulary** is a fixed, versioned ASP contract (`policies/rules/vocabulary.lp`):
`rank(Consumer, R)`, `battery_mode(B, charge|discharge|idle)`, `surplus(sell|store)`,
`grid_charging(yes|no)`. A `DecisionDecoder` turns the answer set into a `Decision` and rejects
incomplete answers.

**Two ways to write rules:**
1. **Structured `RuleSpec`** (JSON, Pydantic, GUI-friendly). Example: *priority = [heat_pump,
   household]; when price_export_band = high and soc_band ≥ mid then surplus = sell; never
   grid_charging when period = HP.* An `AspCompiler` turns it into a `.lp` built on the vocabulary.
   It adds the tie-break pins automatically, so `AmbiguousProgramError` cannot be produced by user
   input.
2. **Raw `.lp`** for experts. It is checked against the same vocabulary contract.

**Pre-run verification.** The fact space is finite: a product of bands. `POST /policies/validate`
solves every combination (memoised by SmartMDAO) and returns:
- a **decision table**, i.e. what the policy does in every situation;
- every **INFEASIBLE** combination, with its `Conflict` from `explain_infeasible`;
- `validate()` findings (`unpinned-program`, `rules-in-cycle`, …);
- a cost quote (`RuleCost.projected_seconds`).

A policy with uncovered situations is rejected before simulation.

## 6. Data: profiles, tariffs, forecasts (`adapters/`)

**`ProfileSource` port:** `list() -> [ProfileMeta]`, `load(ref, grid) -> TimeSeries`.

- `EnedisParquetSource`: reads `/home/wghami/Documents/GroundWorkTesting/enedis_db/*.parquet`.
  - The path is configurable. The columns used are `timestamp` (UTC) and `coefficient_ajuste`.
  - Enedis coefficients have no unit. They are **scaled** to the asset: `kWh_t = coef_t ×
    annual_kWh / Σ coef(reference year)` for consumers, and the same for PV using annual yield
    (kWp × specific yield).
  - The data mixes **30-minute and 15-minute** resolutions, which the resampler handles.
- `EnedisApiSource` (later): wraps the existing fetcher logic (`api_client.py`) behind the same
  port.
- `CsvSource` (upload) and `SyntheticSource` (deterministic, seeded; used in tests).
- `Resampler`: energy series are summed or split proportionally (energy is conserved); power series
  are averaged or held. The resampler handles daylight-saving changes and refuses gaps unless a fill
  strategy is declared.
- `TariffSource` uses the same pattern (flat, HP/HC schedule, CSV/series).
- **`Forecaster` port:** `NoForecast` (default), `Persistence` (same time yesterday or last week),
  `ProfileExpectation` (Enedis coefficient as expectation), `NoisyOracle(sigma)` (for studying the
  value of a better forecast), `PerfectOracle` (benchmarks only).

## 7. API (`api/`, FastAPI + Pydantic v2)

| Method & path | Purpose |
|---|---|
| `GET /catalog/asset-kinds`, `/catalog/profiles`, `/catalog/tariffs`, `/catalog/forecasters`, `/catalog/policies` | Discovery, with JSON schemas generated from the registries |
| `POST /profiles` | Upload a CSV profile |
| `POST /scenarios` · `GET /scenarios/{id}` | Topology + time grid + tariffs + policy + forecaster |
| `POST /policies/compile` | `RuleSpec` → `.lp` preview |
| `POST /policies/validate` | Decision table, conflicts, findings, cost quote (§5.1) |
| `POST /simulations` → `202 {id}` · `GET /simulations/{id}` | Run as a job; returns status and progress |
| `GET /simulations/{id}/result` (`?format=json\|parquet\|csv`) | Time series, KPIs, decision trace |

- Request and response models live in `api/schemas`. They are **separate from domain types**, and
  mappers translate between the two.
- Asset configs are **discriminated unions** on `kind`, generated from the plugin registry, so a new
  asset kind appears in the API without touching the routers.
- `JobRunner` port: v1 runs in-process (thread or process pool, with a timeout). It can be replaced
  by arq or Celery later. `ScenarioRepository` port: in memory or files in v1, SQLite later.

## 8. Architecture & code organisation

```
src/myenergy/
  domain/          # time, series, assets, topology, tariffs, state, decision, flows, kpis  (pure)
  ports/           # Protocols: ProfileSource, TariffSource, Forecaster, DispatchPolicy,
                   #            ScenarioRepository, JobRunner, Clock
  engine/          # simulator, observer/history view, physics (SmartMDAO step pipeline), hooks
  policies/
    baseline.py
    rules/         # vocabulary.lp, spec.py (RuleSpec), compiler.py, decoder.py, verifier.py, rule_policy.py
  adapters/
    profiles/      # enedis_parquet.py, csv.py, synthetic.py, resample.py
    tariffs/  forecasters/  storage/  jobs/
  plugins.py       # typed registries + entry-point discovery
  bootstrap.py     # composition root: the ONLY place concrete classes are wired
  settings.py      # pydantic-settings (paths, defaults, lag, limits)
  api/             # app factory, routers, schemas, mappers, dependency providers
tests/  unit/ property/ integration/ api/  contract/ (every adapter passes its port's contract suite)
```

**Modern Python conventions:**
- Python 3.12:
  - PEP 695 generics and `type` aliases.
  - `typing.Protocol` for every port.
  - Frozen, slotted dataclasses in the domain; Pydantic only at the boundaries.
  - `StrEnum`, `match`, `Self`, `@override`.
- **Dependency injection:**
  - Constructor injection everywhere.
  - A single composition root (`bootstrap.py`) built with **dishka** (scopes: app / request /
    simulation). It integrates with FastAPI.
  - No service locators and no globals.
- **Plugins:** `Registry[T]` keyed by `kind`, filled from `importlib.metadata` entry points
  (`myenergy.assets`, `myenergy.profiles`, `myenergy.policies`, …). Third-party packages can
  extend the app without forking it.
- **Quality gates:**
  - `ruff` (lint + format) and `pyright --strict` (or mypy strict).
  - `pytest` + `hypothesis` + `pytest-cov` (target ≥ 95 % on domain, engine and policies).
  - **`import-linter`** contracts: `domain` imports nothing internal; `engine`/`policies` → `ports`
    and `domain` only; `api`/`adapters` are never imported inward.
  - `pre-commit`.
- Logging is structured (`structlog`). Errors are typed exceptions per layer, mapped to RFC 9457
  problem+json in the API.

## 9. Extension walkthroughs (acceptance test for modularity)

| To add… | You write… | You do NOT touch… |
|---|---|---|
| A second household | Config: another `Site` in the `Topology` + allocation key | Any code (once M6 adds sharing) |
| An EV charger asset | `EVCharger` class + config schema + physics edge rules, registered as plugin | Simulator, API routers, other assets |
| Tempo tariff | `TempoTariff` adapter | Domain, engine |
| A spot-price forecast | `Forecaster` adapter | Policies |
| An MPC policy | `DispatchPolicy` implementation | Engine, API |

## 10. Milestones

- **M0:** project skeleton, tooling, import-linter contracts, CI script.
- **M1:** `TimeGrid`, `TimeSeries`, resampler, Enedis/CSV/synthetic profile sources, tariffs.
- **M2:** physics + baseline policy + simulator + KPIs, with energy-balance property tests.
- **M3:** rules: vocabulary, `RuleSpec` → ASP compiler, `RulePolicy` via SmartMDAO, pre-run
  verifier.
- **M4:** FastAPI layer, jobs, result export.
- **M5:** forecasters + forecast-aware rule facts; no-future-leak tests.
- **M6:** oracle and MPC policies, scenario campaigns (SmartMDAO sweep), community topology.
- **M7:** GUI (to be discussed).

## 11. Verification strategy

- **Golden scenarios:** hand-computed one-day cases (sunny / cloudy / no battery) with exact
  expected flows and bill.
- **Property tests:** energy conservation, SoC bounds, and monotonicity (more PV never raises the
  bill under greedy).
- **Policy tests:** every structured-rule construct compiles; the verifier finds planted conflicts;
  decisions match the decision table.
- **Causality test:** a forecaster or policy that tries to read `t+1` raises an error.
- **API tests:** `httpx` + FastAPI app factory, with the container overridden by fakes (proves the
  DI works).

## 12. Decisions (agreed 2026-10-24)

1. DI container: **dishka**.
2. Observation mode is a **switch** on the scenario: `observation: "lagged" | "ideal"` (lagged =
   last metered step, the default; ideal = current step visible). Implemented as two `Observer`
   strategies.
3. Grid → battery charging is **allowed**, gated by the `grid_charging` rule atom.
4. Enedis profiles are **scaled to annual kWh**; **PRD3 = PV production**. PV production must also
   be pluggable from weather/irradiance APIs: NASA POWER, and the European ones (PVGIS from
   EU JRC, Open-Meteo). These sit behind an `IrradianceSource` port, and a `PVModel` (e.g. pvlib)
   turns irradiance into a production `ProfileSource`.
5. Persistence in v1: in-memory / files.
6. Package name: `myenergy`.
