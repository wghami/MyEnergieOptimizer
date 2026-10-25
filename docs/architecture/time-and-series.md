# Time and series

Design: SPEC §3 and decisions 7–12. Notebooks:
[01 — Time grid](../notebooks/01-time-grid.ipynb),
[02 — Time series and resampling](../notebooks/02-time-series-and-resampling.ipynb).

## `TimeGrid` (`myenergy.domain.time`)

A half-open range `[start, end)` **held in UTC**, cut into equal steps of 5, 10, 15, 20, 30 or 60
minutes. Each step is labelled by its start.

| Rule | Why |
|---|---|
| UTC storage; `timezone` (default `Europe/Paris`) kept for wall-clock questions | daylight-saving days are just 23- or 25-hour local days; nothing to special-case |
| the step divides an hour | every grid of a given step lines up with every other one |
| the start is aligned on the step, the span is a whole number of steps | no partial steps exist, so no rounding rule is needed |
| naive datetimes are refused | a time without an offset is ambiguous around daylight-saving changes |

Invalid grids raise `GridError` with the reason; nothing is rounded silently.

## `TimeSeries` (`myenergy.domain.series`)

One finite value per step, read-only, tagged with a `Quantity`:

| Quantity | Meaning | Combines by | Resamples by |
|---|---|---|---|
| `POWER_KW` | average power over the step | addition with power | time-weighted mean |
| `ENERGY_KWH` | energy within the step | addition with energy; `total()` | sum / proportional split |
| `PRICE_EUR_PER_KWH` | price during the step | addition with prices | time-weighted mean |
| `DIMENSIONLESS` | a shape, e.g. an Enedis coefficient | scaling into kW | time-weighted mean |

Profiles are held as power because power does not depend on the step: one profile serves every
grid, and `energy()` multiplies by the step length when kWh are needed.

## Resampling

One method serves every pair of grids, including steps that do not divide each other. The series
is turned into its running integral at the source step edges (exact, because values are constant
within a step), the integral is read at the target edges by linear interpolation, and the
differences give the target values. Consequences, checked by property tests:

- energy over the period is conserved for any pair of steps;
- the time-weighted mean of a rate is conserved;
- refining a grid and coarsening it back returns the original values.

A target grid that reaches outside the series raises `CoverageError` naming both ranges
(decision 9): data is never extrapolated.
