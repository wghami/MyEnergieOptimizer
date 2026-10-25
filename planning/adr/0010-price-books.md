# 0010 — Price books are data, bases are plugins, network charges may be included

Status: accepted
Date: 2026-10-25

## Context

M2 task 4 needs a way to say what a bill charges: network tariff, taxes, supplier prices,
services, feed-in revenue. Nothing country- or offer-specific may be hard-wired (ADR 0008). A real
French bill bundles the network tariff into the supplier's prices and shows CTA, excise and VAT
separately, with the network total "for information".

## Decision

- A price book is TOML: lines with a basis, a flow, a schedule, a rate reference with selector
  templates (`{field}`, `{subscribed_kva}`, `{period}`, basis placeholders such as `{tier}`), a
  VAT category, a credit flag, an inclusion (`itemised` or `included`) and a `when` condition.
- Two layers merged by line name: the pack's regulated book and the user's supplier book (with
  `remove`). A user's book carries its own dated prices in the rate-file format, with a new
  status `user`.
- Bases are plugins (`myenergy.price_bases`): `fixed`, `per_kwh`, `tiered_per_kwh`, `percent_of`,
  `once`. Services are `fixed` lines priced per month (new unit `EUR/month`); one-off fees use
  `once` (unit `EUR`).
- `included` lines are computed and shown but not added; `percent_of` by name may use them (CTA
  on the bundled TURPE fixed part), VAT by category takes only itemised lines. `fr-household`
  sets the `network` layer `included` by default.
- Proration by days / 365, rounding to the cent per line and VAT on rounded lines are book
  settings.
- Resolution against a contract and a period is separate from computation (task 5) and reports
  every problem at once.

## Consequences

- CTA, VAT, excise and TURPE are data of the French pack; another country or a research scenario
  changes files, not code.
- Collective-energy excise needed versions before its 2025-03-01 exemption (the normal rate, to
  verify), found by the golden test that resolves every allowed contract.
- Harder: basis parameters are untyped TOML values checked by each basis; mistakes surface at
  resolution with a message, not from the type checker.

## Alternatives considered

Supply and network as fixed bill sections in code (rigid, French-specific). Separate files for a
user's prices and lines (two files to keep in step for one offer).
