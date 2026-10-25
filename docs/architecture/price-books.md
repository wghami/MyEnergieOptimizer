# Price books

Design: SPEC §3.1, ADR 0010, [M2](https://github.com/wghami/MyEnergyOptimizer/blob/main/planning/milestones/M2.md).
Amounts and bills come with M2 task 5; this page covers the book itself and its resolution.

A **price book** is a list of **lines**; no charge, tax or rate is written in code. A tariff pack
ships its regulated book (`price-book.toml` beside `pack.toml`); a user's book adds a supplier's
lines and **dated prices** in the same file.

```toml
[book]
name = "my-supplier"
remove = []                                   # lines of the pack's book to drop
inclusion = { network = "included" }          # default per layer: itemised | included
settings = { proration_days = 365, rounding = 0.01, vat_on_rounded = true }

[[lines]]
name = "supply.energy"
layer = "supply"
payee = "supplier"
basis = "per_kwh"
flow = "supplied"
schedule = "supply"
rate = { component = "supply.energy", selectors = { option = "{supply_option}", period = "{period}" } }
vat = "consumption"

[sources.offer]
title = "My supplier's price list"            # a URL is optional for user prices

[[rates]]
component = "supply.energy"
selectors = { option = "hp-hc" }
unit = "EUR/kWh"
by = "period"

[[rates.versions]]
from = 2025-08-01
source = "offer"
status = "user"
value = { HP = 0.20, HC = 0.15 }
```

## A line (`myenergy.domain.pricebooks.PriceLine`)

| Key | Meaning |
|---|---|
| `name`, `layer`, `payee` | identity; `layer` is a free label (supply, network, tax, service, ...) |
| `basis` | how the amount is built (below); bases are plugins |
| `flow`, `counterparty` | the flow charged ([Sites and energy flows](sites-and-flows.md)); shared flows may name a counterparty |
| `schedule` | `network` or `supply` (the contract's schedules, from its pack) or a named schedule; its periods split the line |
| `rate` | a component and selector **templates**: `{field}` takes a contract field, `{subscribed_kva}` the power, `{period}` each schedule period, `{tier}` each tier of a tiered line |
| `vat` | the VAT category whose VAT line charges this line |
| `credit` | revenue (sold or shared-out energy): a negative amount |
| `inclusion` | `itemised` (added to the total) or `included` (inside other prices: shown as "of which", not added); default from the book's `inclusion` per layer, else itemised |
| `when` | `{ field = [values] }`: the line applies only to matching contracts |

## Bases (`myenergy.ports.pricing.PriceBasis`, group `myenergy.price_bases`)

| Basis | Amount | Rate units |
|---|---|---|
| `fixed` | a yearly or monthly charge, per kVA if the rate is, prorated over the bill period | EUR/year, EUR/kVA/year, EUR/month |
| `per_kwh` | the flow in each period times that period's rate | EUR/kWh |
| `tiered_per_kwh` | price per tranche of energy accumulated over `reset` (`month`, `year`, `bill`); `tiers = [{ name, up_to_kwh }, ..., { name }]` | EUR/kWh |
| `percent_of` | a share of other lines: `of = [names]` (itemised or included) or `of_vat = "category"` (itemised lines of that category) | fraction |
| `once` | a one-off amount per bill | EUR |

A new kind of charge (say a power-overrun charge for businesses) is a new basis plugin.

## Pack book + user book

`with_user_book(packs, pack, user)` merges the user's book onto the pack's (a same-named line
replaces the pack's; `remove` drops lines; layer defaults merge; the user's settings win when
given) and layers the user's prices on the pack's rates. Packs extend each other's books the same
way.

## Bundled or itemised network charges

French suppliers that follow the regulated tariff bundle the network tariff (TURPE) into their own
subscription and kWh prices; only CTA, excise and VAT appear separately. The `fr-household` book
therefore marks the `network` layer `included`: TURPE lines are computed and shown as "of which",
not added. They stay a base for `percent_of` by name (the CTA is a share of the TURPE fixed part),
but VAT by category takes only itemised lines. An offer that bills TURPE separately sets
`inclusion = { network = "itemised" }`.

## Resolution (`myenergy.engine.pricing.PriceBookResolver`)

`resolve(book, PricingContext(contract, pack, rates, start, end, schedules, allow_to_verify))`
keeps the lines whose `when` holds, finds each line's schedule periods and concrete rate keys,
checks each rate covers the whole period with the basis's unit and an allowed status (`official`
or `user`; `to-verify` only when allowed), records where rates change inside the period (bills are
split there, as on real bills), and orders lines so a percentage follows what it is a percentage
of. **Every** problem is reported at once (`PriceBookError.problems`): unknown basis or schedule,
bad parameters, missing flow or rate, wrong unit, a gap in coverage, an unverified rate, an unknown
or circular reference, an empty period.

## Settings

Fixed charges are prorated by days / 365 (checked against a real bill; leap years to verify),
each line is rounded to the cent, and VAT is computed on rounded lines. All three are book
settings (`proration_days` may be `"actual"` for the length of each year).
