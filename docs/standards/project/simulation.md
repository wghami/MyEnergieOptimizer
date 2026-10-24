# Simulation — MyEnergieOptimizer

## Information and decisions

| ID | Rule | Enforced by |
|---|---|---|
| MEO-SIM-1 | **Causality.** Policies and forecasters only receive a `HistoryView`; reading beyond the observable step raises `FutureAccessError`. | `tests/property/` causality tests |
| MEO-SIM-2 | The observation mode is a switch on the scenario: `lagged` (default: the last metered step) or `ideal` (the current step is visible). Each is a separate `Observer` strategy. | contract tests of the `Observer` port |
| MEO-SIM-3 | A `Decision` is a **policy** for the step (priorities, battery modes, sell or store, grid charging), never a kWh setpoint. Physics applies it to the *realised* values, so a wrong expectation costs money but never breaks the balance. | type design, review (ADR 0003) |
| MEO-SIM-4 | Knowledge of the future reaches a policy only through an explicit `Forecaster`. `PerfectOracle` exists for benchmarks only and is refused in normal scenarios. | API validation, tests |

## Physical invariants

| ID | Rule | Enforced by |
|---|---|---|
| MEO-SIM-5 | Energy balance per node and per step holds to 1e-9 kWh, losses included. | Hypothesis property tests |
| MEO-SIM-6 | `soc_min ≤ SoC ≤ soc_max`; battery power limits hold; no flow is negative; a meter never imports and exports in the same step. | Hypothesis property tests |
| MEO-SIM-7 | The same scenario and seed always give bit-identical results. | golden tests |
| MEO-SIM-8 | Resampling conserves energy for energy series and averages power series. Gaps are refused unless a fill strategy is declared. Daylight-saving transitions are handled explicitly. | property tests of the resampler |

## SmartMDAO

| ID | Rule | Enforced by |
|---|---|---|
| MEO-SIM-9 | The per-step pipeline passes `smartmdao.validate()` with no findings when it is built; otherwise the simulation is refused before it starts. | engine code, integration test |
| MEO-SIM-10 | Rule programs stay off feedback loops (`rules-in-cycle` is an error), and floats never reach ASP: thresholds are declared `Bands`. | `validate()` (MEO-SIM-9), SmartMDAO itself |
| MEO-SIM-11 | Rule programs are pinned (optimisation plus a total tie-break), so `AmbiguousProgramError` cannot be triggered by user input. Generated programs get the tie-break automatically. | compiler tests |
| MEO-SIM-12 | Before a simulation, a policy is verified over its whole finite fact space: decision table, `INFEASIBLE` combinations with their `Conflict`, and a cost quote. A policy with uncovered situations is refused. | verifier tests |
