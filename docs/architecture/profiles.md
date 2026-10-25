# Profiles

Design: SPEC §6 and decisions 7, 9, 10, 12. Notebook:
[03 — Load and PV profiles](../notebooks/03-load-and-pv-profiles.ipynb). Script:
[`scripts/export_profile.py`](../scripts.md).

A **profile** says how much power a consumer draws, or a PV array produces, at every step. It is
described by a **spec** and resolved into a kW series on any grid.

```text
Shaped(ref, scaling) ──► ProfileResolver ──► ProfileSource.shape(key, grid) ──► shape × factor = kW
        │                     (engine)              (port; Enedis, CSV, synthetic, …)
        └── scaling: Nominal | Calibrated | PVSystem → one constant factor
```

## Shapes and sources (`myenergy.ports.profiles`)

A **shape** is dimensionless, with a mean of about 1 over a year (an Enedis coefficient, a
synthetic curve). Every `ProfileSource` honours one contract, which `tests/contract/` checks for
each implementation, including a test-only plugin:

- `catalog()` lists its profiles (`ProfileMeta`: key, kind, coverage, native timestamp label);
- `shape(key, grid)` returns the shape **on exactly `grid`**, labelled by interval start;
- outside the data → `CoverageError`; an unknown key → `UnknownProfileError`.

`InMemoryProfileSource` holds already-loaded shapes; file-based sources load into it.

| Source | Reads | Rules |
|---|---|---|
| `EnedisParquetSource` | a folder of `<Category>_<SUBPROFILE>.parquet` files (`ENEDIS_DB_PATH`) | column `coefficient_ajuste` by default; 30-minute values (until 2024-10-04 22:00 UTC) are held over their interval on the 15-minute step; gaps, duplicates or missing values are errors. `Producteur` files are production, the rest consumption |
| `CsvProfileSource` | user CSV files with exactly `timestamp,value` | offset-aware timestamps, one regular step dividing an hour, finite values, ≤ 20 MiB; unit `1` (shape), `kW` or `kWh` per step (converted to kW); `end`-labelled files are moved back one step. Every error names the file and line |
| `SyntheticProfileSource` | nothing: generated | `household` (two peaks, winter-heavy, seeded noise), `pv-clear-sky` (solar elevation at a location), `constant`; mean 1 over 2021; the same value whatever the requested window |

Measured profiles (CSV in `kW`/`kWh`) have unit `kW` and take `AsMeasured()` or `Calibrated`; shapes take
`Nominal`, `PVSystem` or `Calibrated`. Any other pairing is refused.

**Data quality is shown, not repaired.** The Enedis `PRD3_BASE` data has solar values around midnight
on 2024-10-05 (a probable 12-hour shift at the resolution switch); see notebook 03 and
`tests/fixtures/enedis/README.md`.

## Scaling: one constant factor

| Scaling | Factor (kW per shape unit) | Use |
|---|---|---|
| `Nominal(annual_kwh)` | annual_kwh / 8760 h | the default; year-to-year variation in the data is kept |
| `Calibrated(energy_kwh, window)` | energy ÷ shape energy over `window` | a known consumption over any period: a billing year starting in November, a month, a week |
| `PVSystem(peak_kwp, specific_yield)` | `Nominal(peak × yield)` | simple PV sizing until a PV API computes production |
| `AsMeasured()` | 1 | measured kW (a meter export) |

Because the factor is a constant, a simulation of a day, a month or 14 months, at any step,
evaluates `shape × factor` on its own grid: nothing is renormalised per period. Calibration is
exact over its window for any step (resampling conserves energy).

## Time shift

`ProfileRef(source, key, time_shift)` moves a curve later on purpose: the value used at `t` is the
source's value at `t − time_shift`. It must be a whole number of grid steps; anything else is a
`GridError`. Without a shift, nothing moves (decision 10: Enedis timestamps mark interval starts).

## Extension: PV APIs

PVGIS or NASA POWER will compute production instead of scaling a shape. They will add a new spec
type to `ProfileSpec` and a branch in the resolver, behind the same `power(spec, grid)` call, so
nothing that consumes profiles changes.
