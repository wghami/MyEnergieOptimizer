# Wiring: settings, plugins and the container

Design: ADR 0002 (dishka), MEO-DI-1…4, MEO-PLG-1…4.

```text
environment / .env ──► Settings ──┐
                                  ├──► AppProvider (dishka, APP scope) ──► Mapping[str, ProfileSource]
entry points ──► Registry[plugin] ┘                                    ├─► ProfileResolver
                                                                       └─► RateSource
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
| `MYENERGY_RATE_SOURCE` | the rate source to use (default `toml`, the packaged tables) |
| `MYENERGY_SOURCES__TOML__ROOT` | a folder of TOML rate files used instead of the packaged tables |

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

Rate sources work the same way through the `myenergy.rate_sources` group and the
`RateSourcePlugin` protocol (`create(options) -> RateSource`); exactly one is used, the one named by
`MYENERGY_RATE_SOURCE` ([Rates](rates.md)).

## The container (`myenergy.bootstrap`)

`make_app_container(settings=None, plugins=None, rate_plugins=None)` is the **only** place where
concrete adapters meet the ports (import contract MEO-ARC-2). It provides `Settings`, the
configured `Mapping[str, ProfileSource]`, the `ProfileResolver` and the selected `RateSource`.
Tests pass their own settings and plugin registries; nothing is monkey-patched (DI-3). Close the
container when done.
