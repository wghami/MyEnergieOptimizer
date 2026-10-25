# 0008 — Tariff frameworks are user-definable packs of data

Status: accepted
Date: 2026-10-25

## Context

After ADR 0007 the schedules were generic, but the contract still hard-wired the French household
framework: the network options (CU4, …) as a closed enum, the 36 kVA limit, statuses, the TURPE
seasons and the 8-hour rule, and one global rate source. The user asked that nothing make the code
rigid: another country should need minimal changes, and users must be able to define their own
framework for research or tax studies. A pack may be tagged with a country, but country must not
be the only tag.

## Decision

- A **tariff pack** is data: `pack.toml` (fields with allowed values and defaults, a power
  limit, declarative checks, how the network schedule is built, supply options, free tags), a
  `rates/` folder and an optional `schedules.toml`.
- The domain `Contract` is generic: pack name, subscribed power, free fields (which double as rate
  selectors), off-peak hours (general and per season), optional explicit network and supply
  schedules. `TariffPack.contract()` validates it; `network_schedule()` and `supply_schedule()`
  build its schedules.
- Checks are data (`when` / `require` / `off_peak_hours`, level `error` or `warning`).
- A pack may **extend** another: tags and fields merge, other sections are replaced when given,
  rate keys and schedules redefined by the child hide the parent's (`LayeredRateSource`).
- Packs come from a `PackSource` port; `TomlPackSource` reads the built-in folder and the folders
  in `MYENERGY_PACK_ROOTS`. Free tags describe packs; `tagged()` filters them.
- The French household framework becomes the built-in `fr-household` pack; its rate tables move
  into it. The global rate-source selection (`MYENERGY_RATE_SOURCE`, the `myenergy.rate_sources`
  plugin group) and `domain/time_classes.py` are removed: rates belong to packs.

## Consequences

- A new country, offer family or research scenario is a folder, not a code change.
- Bills (M2 task 4 onward) select rates through contract fields and pack data only.
- Harder: field names and values are strings checked at the boundary instead of enums checked by
  the type checker; a typo in a pack is caught when the pack is loaded or a contract is made, not
  by pyright. The checks DSL is deliberately small; richer rules may need extending it.

## Alternatives considered

One code plugin per country (entry points): needs Python to adapt anything and ties packs to
countries. Keeping enums in the domain with a pack only for rates: still rigid for fields and
checks.
