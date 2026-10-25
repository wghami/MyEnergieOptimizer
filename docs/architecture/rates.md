# Rates

Design: SPEC §3.1, ADR 0006, [M2](https://github.com/wghami/MyEnergyOptimizer/blob/main/planning/milestones/M2.md).
Research: `planning/research/french-household-electricity-bill.md`.

Every regulated price on a bill (network tariff, CTA, excise, VAT) is **dated data** with a source
and a status, never a constant in code. A bill period that crosses 1 February or 1 August simply
uses two versions.

```text
TOML tables (packaged) ─┐                                   RateKey(component, selectors)
a database (M9, later) ─┼──► RateSource (port) ──► RateHistory ──► .on(day) ──► RateVersion
a test-only source ─────┘                                                     value, unit, source,
                                                                              status, validity
```

## Keys, versions, histories (`myenergy.domain.rates`)

- A **`RateKey`** names what is priced: a component and its selectors, for example
  `turpe.withdrawal.energy[fta=CU4, segment=BT<=36kVA, time_class=HPH]`.
- A **`RateVersion`** is one value over `[valid_from, valid_to)` (`None`: still valid), in a
  canonical `RateUnit` (`EUR/year`, `EUR/kVA/year`, `EUR/kWh`, `fraction`), held as `Decimal` so
  it reads exactly as published. It cites its **source** and has a **status**: `official` or
  `to-verify`.
- A **`RateHistory`** holds the versions of one key: one unit, no overlap (gaps are allowed).
  `on(day)` returns the version valid that day, raises `CoverageError` when none is, and raises
  `UnverifiedRateError` for a `to-verify` version unless `allow_to_verify=True` is passed.

## Components and selectors

| Component | Selectors | Unit | Meaning |
|---|---|---|---|
| `turpe.management` (CG) | `segment`, `status` (`consumer`, `collective`, `producer-injection`), `contract` (`supplier`, `user`) | EUR/year | management component, Rf or Ccard included |
| `turpe.metering` (CC) | `segment`, `meter` (`metered`, `unmetered`) | EUR/year | metering component |
| `turpe.withdrawal.power` (b) | `segment`, `fta` (`CU`, `CU4`, `MU4`, `MUDT`, `LU`, `CU4-AC`, `MU4-AC`) | EUR/kVA/year | times the subscribed kVA |
| `turpe.withdrawal.energy` (c) | `segment`, `fta`, `time_class` (`HPH`, `HCH`, `HPB`, `HCB`), and `origin` (`grid`, `collective`) for the `-AC` options | EUR/kWh | per kWh withdrawn in the class |
| `cta` | `network` (`distribution`) | fraction | of the TURPE fixed part (CG + CC + b × P) |
| `excise` | `category` (`household`), `origin` (`grid`, `collective`) | EUR/kWh | accise sur l'électricité |
| `vat` | `base` (`subscription`, `consumption`) | fraction | subscription: fixed charges and CTA; consumption: energy and excise |

Every network option has the four time classes, so callers never special-case: a flat option (CU,
LU) repeats one value, and MUDT repeats its HP and HC values in both seasons, exactly as Enedis
publishes them. The `-AC` options are those of collective self-consumption below one HTA/BT
substation: energy from the operation (`origin=collective`) pays a lower rate than energy from
the grid.

## The French tables (`fr-household` pack)

Rates belong to a [tariff pack](packs.md). `TomlRateSource` reads a pack's `rates/` folder: one file per TURPE deliberation (`turpe6-2024-08-01.toml`,
`turpe6-2025-02-01.toml`, `turpe7-2025-08-01.toml`, `turpe7-2026-08-01.toml`) and `taxes.toml`.
Coverage starts on **2024-08-01**. Each file cites its documents under `[sources.<id>]`; values are
written in the published unit (`cEUR/kWh`, `EUR/MWh`, `%`, …) and converted exactly on load. A
version without `to` lasts until the next version of the same key, so adding a deliberation means
adding one file. Files are size-limited and schema-checked; anything malformed is a
`DataFormatError` naming the file.

The tables are checked twice by `tests/golden/test_rate_tables.py`: against reference values typed
again from the texts, and against the texts' own arithmetic (TURPE 6 fixed coefficients are
multiples of 0.12 €; TURPE 7 rose by exactly 3.04 % on 2026-08-01).

The only `to-verify` value today is the zero excise on energy shared in a collective
self-consumption operation (from 2025-03-01).

## Where rates come from

Each [tariff pack](packs.md) holds its rates in its `rates/` folder; `PackSource.rates(name)`
returns them, those of the packs it extends included (a key redefined by a pack hides the
inherited history). The `RateSource` port stays the same for a future database of rates.
