# Wiring: settings, plugins and the container

Design: ADR 0002 (dishka), MEO-DI-1…4, MEO-PLG-1…4.

```text
environment / .env ──► Settings ──┐
                                  ├──► AppProvider (dishka, APP scope) ──► Mapping[str, ProfileSource]
entry points ──► Registry[plugin] ┘                                    ├─► ProfileResolver
                                                                       ├─► PackSource
                                                                       ├─► SiteResolver
                                                                       └─► PriceBookResolver
```

## Settings (`myenergy.bootstrap.settings`)

Read from the environment, or a git-ignored `.env` file (SEC-7). Each profile source reads its own
options from `MYENERGY_SOURCES__<SOURCE>__<OPTION>`:

| Variable | Meaning |
|---|---|
| `MYENERGY_SOURCES__ENEDIS__ROOT` (or `ENEDIS_DB_PATH`) | folder of Enedis parquet files; without it the Enedis source is off |
| `MYENERGY_SOURCES__ENEDIS__COLUMN` | coefficient column (default `coefficient_ajuste`) |
| `MYENERGY_SOURCES__SYNTHETIC__SEED` | seed of the synthetic household noise (default 0) |
| `MYENERGY_SOURCES__SYNTHETIC__LATITUDE`, `…__LONGITUDE` | location of the clear-sky PV curve (default Paris) |
| `MYENERGY_PACK_ROOTS` | folders of user-written [tariff packs](packs.md), as a JSON list, beside the built-in ones |

## Plugins (`myenergy.ports.plugins`)

A profile source joins the application through a **plugin**: an object with a `name` and
`create(options) -> ProfileSource | None` (`None` when the source is not configured). Plugins are
**entry points** of the `myenergy.profile_sources` group, built-ins included, so a third-party
package adds a source without touching this repository:

```toml
[project.entry-points."myenergy.profile_sources"]
pvgis = "my_package.plugins:PVGIS"
```

`load_entry_points` checks each one against the `ProfileSourcePlugin` protocol before use.

Asset kinds work the same way through the `myenergy.asset_kinds` group and the `AssetKind`
protocol ([Sites and energy flows](sites-and-flows.md)), and price bases through the
`myenergy.price_bases` group and the `PriceBasis` protocol ([Price books](price-books.md)).

Tariff packs need no code at all: they are folders of data found in the built-in pack folder and
in `MYENERGY_PACK_ROOTS` ([Tariff packs](packs.md)).

## The container (`myenergy.bootstrap`)

`make_app_container(settings=None, plugins=None, asset_kinds=None, price_bases=None)` is the **only** place where
concrete adapters meet the ports (import contract MEO-ARC-2). It provides `Settings`, the
configured `Mapping[str, ProfileSource]`, the `ProfileResolver`, the `PackSource` and the
`SiteResolver` (with every installed asset kind) and the `PriceBookResolver` (with every
installed price basis).
Tests pass their own settings and plugin registries; nothing is monkey-patched (DI-3). Close the
container when done.
