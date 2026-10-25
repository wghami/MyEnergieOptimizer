# 0006 — Dated rates are read through a port, stored as TOML now and in a database later

Status: accepted (storage location amended by ADR 0008: rates belong to tariff packs)
Date: 2026-10-25

## Context

Bills need official rates that change on fixed dates (TURPE every 1 August and sometimes 1 February,
excise and CTA by law, VAT by reform). M2 needs a handful of versions; M9 adds an agent that fetches
rates and proposes new versions. Its findings must be stored durably and recovered by the inputs
that select a rate: component, date, subscribed kVA, tariff option, network option (FTA) and
customer status. Values found by the agent stay `to-verify` until a human confirms them (SPEC
decision 14).

## Decision

- The domain defines `RateKey` (component + selectors) and `RateVersion` (value, unit, validity
  `[from, to)`, source document, status). Lookup is exact: no interpolation, no "latest known".
- The `RateSource` port lists its keys (`catalog()`) and returns a key's `RateHistory`
  (`history(key)`). The history refuses overlapping versions when it is built, and `on(day)`
  raises when no version covers the day.
- M2 ships a **packaged-TOML adapter**: one file per TURPE deliberation plus one for taxes,
  reviewed in pull requests. A version without an end date lasts until the next one starts.
- M9 adds a **database adapter** (SQLite first) behind the same port, with the same keys indexed,
  and the agent writes only `to-verify` rows. The TOML files can seed it.
- The engine refuses `to-verify` versions in a bill unless the caller allows them explicitly.

## Consequences

- Swapping storage is a wiring change; the bill engine never sees files or SQL.
- One contract test suite runs against every `RateSource`.
- Harder: selectors must be designed up front (kVA bands, FTA codes, statuses) so that both stores
  agree; adding a selector later is a schema change.

## Alternatives considered

Rates as Python constants (no provenance, edits need code review of logic); a database from M2
(storage and migration cost before anything writes to it).
