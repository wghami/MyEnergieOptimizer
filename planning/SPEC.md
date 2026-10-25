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
5. **Nothing country- or offer-specific is hard-wired.** Regulated structures (time classes,
   rate components, contract rules) are data or plugins on generic types, so a new offer or
   another country needs as few code changes as possible; norms that do not prevent pricing are
   warnings, not errors (ADR 0007). Tariff frameworks are user-definable **packs** of data, tagged
   freely (country is one tag among others), which may extend one another (ADR 0008).
6. **Checked before it runs** (the SmartMDAO ethos). Before any simulation, a policy is validated
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

- **`TimeGrid`**: half-open `[start, end)` in UTC, a `step` that divides 60 minutes (5, 10, 15,
  20, 30 or 60 min), and a `timezone` (default `Europe/Paris`) used only for wall-clock logic
  (seasons, peak/off-peak hours). It provides the step index ↔ timestamp mapping. Daylight-saving
  days have 23 or 25 local hours and need no special case.
- **`TimeSeries`**: a read-only numpy array on a `TimeGrid`, tagged with a **quantity**:
  `POWER_KW` (average power over the step, the internal form of profiles), `ENERGY_KWH`,
  `PRICE_EUR_PER_KWH` or `DIMENSIONLESS`. Arithmetic is only allowed between compatible series on
  the same grid. **Resampling** uses one overlap-weighted method for any pair of steps:
  time-weighted means for power, price and shapes; sums and proportional splits for energy.
- **Assets** are data in a site file, by kind; each kind is a plugin with a role (source, sink,
  storage), registered in `myenergy.asset_kinds` (ADR 0009). First sketch of the kinds:
  - `Consumer(id, load: ProfileRef, priority_class?)`
  - `PVArray(id, production: ProfileRef)`
  - `Battery(id, capacity_kwh, p_charge_max_kw, p_discharge_max_kw, eta_charge, eta_discharge, soc_min, soc_max, soc_initial)`
  - `GridConnection(id, contract, import_prices: PriceBook, export_prices: PriceBook)`
- **`Site`**: a group of assets behind one meter, described in TOML with its contract and shares;
  its meter flows (`SiteFlows`) are what bills charge (ADR 0009). **`Topology`**: sites plus (later) shared assets
  and an allocation key. v1 = `Topology(sites=[one_site])`.
- **Prices and bills** (M2, see §3.1 and `research/french-household-electricity-bill.md`): a
  **price book** of dated components (supply, network, CTA, excise, VAT…), charged **per energy
  flow** (grid import, self-consumption, collective sharing, export).
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

### 3.1 Prices and bills (M2)

- **Rate tables are dated data**, versioned in the repository: every value has a source, an
  effective period and a status (`official` or `to verify`). A `to verify` value cannot be used in a
  simulation. Rates are read through the `RateSource` port (ADR 0006): packaged TOML now, a
  database filled by the M9 agent later, both queried by component, date, kVA, option, FTA and
  status. French household tables (TURPE 7 ≤ 36 kVA, CTA, excise, VAT) come first; companies
  later, as more data and components in the same structure.
- **Contract**: generic data under a **tariff pack** (ADR 0008): subscribed power, free fields
  that double as rate selectors (for the French pack: network option such as CU4, status, who
  holds the access contract, meter, supply option), the connection's off-peak hours (per season if
  they differ), and optional explicit network and supply schedules (ADR 0007). The pack checks the
  fields and builds the schedules.
- **Price book**: components, each with a layer (supply, network, CTA, excise, VAT, levy), a payee,
  a basis (`per_kwh` flat / time-of-use / series, `per_period` fixed, `tiered_per_kwh` by
  accumulated consumption in a declared period, `percent_of` named lines), the flows it applies to,
  and values that may depend on the contract (`by_power_kva`) and on dates. Users write price books
  in TOML, validated at the boundary.
- **Energy flows** are what get charged: grid import, on-site self-consumption, energy received
  from a collective operation (*autoproduite*), export to the grid. The same kWh has different
  values on each.
- **One model, two directions:**
  - *forward*: price book + flows → an **itemised bill** (lines by layer, payee, flow and period)
    and the **marginal value of a kWh per flow and step**, which the rules and the optimisation use;
  - *inverse*: a real bill (total incl. VAT, kWh per period, kVA, option, dates) → every regulated
    layer from the official rates, and the **remainder is the supply part**. It explains a user's
    bill, calibrates their supply price, and checks the rate tables: an implausible remainder is
    reported.

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

**`ProfileSource` port:** `catalog() -> [ProfileMeta]` (reference, kind, native resolution,
coverage, timestamp label) and `shape(ref, grid) -> TimeSeries` (dimensionless, mean ≈ 1).

- **Profile specs**: `Shaped(shape_ref, scaling)` (M1) or `Computed(source, params)` (later: PVGIS,
  NASA POWER from a `PVSite(lat, lon, tilt, azimuth, peak_kwp, losses)`). Both yield a kW series
  through the same interface.
- **Scaling turns a shape into kW with one constant factor**, so any simulation period and any
  step work:
  - `Nominal(annual_kwh)` (default): factor = annual_kWh / 8760 h. Year-to-year variation in the
    data (±5 % for PV) is kept, as in reality.
  - `Calibrated(energy_kwh, window)`: factor = energy ÷ ∫shape over the window, which can be any
    period (a billing year starting in October, a month, a week).
  - `PVSystem(peak_kwp, specific_yield_kwh_per_kwp)` → an annual energy, until a PV API computes
    production directly.
- **Nothing passes silently**: a period (or a calibration window) the data does not cover is an
  error. Each source declares `timestamp_label = "start" | "end"` (Enedis: `start`); an explicit
  `time_shift` on a profile reference allows a deliberate shift.
- `EnedisParquetSource`: reads the configured folder (`ENEDIS_DB_PATH`) with pyarrow. Column
  `timestamp` (UTC) and, by default, `coefficient_ajuste` (configurable). The data mixes
  **30-minute (until 2024-10-04 22:00 UTC) and 15-minute** resolutions; the resampler handles it.
- `EnedisApiSource` (later): wraps the existing fetcher logic (`api_client.py`) behind the same
  port.
- `CsvSource` (upload) and `SyntheticSource` (deterministic, seeded; used in tests).
- `Resampler`: energy series are summed or split proportionally (energy is conserved); power series
  are averaged or held. The resampler handles daylight-saving changes and refuses gaps unless a fill
  strategy is declared.
- Prices: see §3.1 (M2).
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
- **M1:** time and profiles: `TimeGrid`, `TimeSeries`, resampling, scaling and calibration,
  Enedis/CSV/synthetic profile sources, first DI container and settings.
- **M2:** prices and bills: dated rate tables (French households), energy flows, price books,
  itemised bills, inverse decomposition, marginal value per flow.
- **M3:** physics + baseline policy + simulator + KPIs, with energy-balance property tests;
  settlement through M2's bills.
- **M4:** rules: vocabulary, `RuleSpec` → ASP compiler, `RulePolicy` via SmartMDAO, pre-run
  verifier.
- **M5:** FastAPI layer, jobs, result export.
- **M6:** forecasters + forecast-aware rule facts; no-future-leak tests.
- **M7:** oracle and MPC policies, scenario campaigns (SmartMDAO sweep), community topology
  (selling to neighbours); weather-API PV sources.
- **M8:** GUI (to be discussed).

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

Agreed 2026-10-25:

7. Profile scaling is `Nominal` (annual kWh / 8760 h) by default, with `Calibrated(energy, window)`
   for any window, including billing years that do not start in January and periods shorter than
   a year.
8. Time steps divide 60 minutes (5, 10, 15, 20, 30, 60 min).
9. Periods outside the data are an **error**; nothing passes silently.
10. Enedis timestamps mark the **start** of the interval; an explicit `time_shift` option exists.
11. Default Enedis column: `coefficient_ajuste` (configurable).
12. PV is specified simply in M1 (kWp × specific yield, or annual kWh) behind a profile spec that a
    PVGIS / NASA POWER provider will fill later.
13. Pricing is a model of its own (M2): dated official rate tables, price books per energy flow,
    forward itemised bills and inverse bill decomposition. Households first; companies later.
14. Official rates are versioned as data with source, effective period and status; a scheduled
    check reminds when a February/August change is due and not entered; `to verify` values are
    unusable in simulations.
15. VAT on sales within a collective operation and income tax on household sales are **open
    questions** (`research/french-household-electricity-bill.md` §7), to settle before modelling
    sales to neighbours (M7).
