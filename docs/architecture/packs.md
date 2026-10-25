# Tariff packs

Design: ADR 0008, SPEC principle 5. Notebook: [05 — Tariff packs](../notebooks/05-tariff-packs.ipynb).

A **tariff pack** is a folder of data that gives a contract its meaning. Nothing specific to a
country, a regulator or an offer is in the code: the built-in `fr-household` pack is one pack, and
users write their own (another country, a research scenario, a tax study), from scratch or by
extending another pack.

```text
my-packs/
└── vat-study/
    ├── pack.toml        fields, checks, network schedule, supply options, tags, extends
    ├── rates/*.toml     dated rates (format: Rates page); may be empty or absent
    ├── price-book.toml  optional regulated price lines (format: Price books page)
    └── schedules.toml   optional named schedules (format: Schedules page)
```

## What a pack holds (`myenergy.domain.packs.TariffPack`)

| Part | `pack.toml` | Meaning |
|---|---|---|
| name, title, tags | `[pack]` | free tags such as `country`, `sector`, `purpose`, `source`; filter with `tagged(packs, country="FR")` |
| extends | `[pack] extends` | inherit another pack (below) |
| power limit | `[pack] max_kva` | optional |
| sharing step | `[pack] sharing_step_minutes` | optional: the step at which sharing schemes allocate energy; flows on another step raise a warning |
| fields | `[fields.<name>]` | allowed `values`, optional `default` (else required), `description`; fields double as **rate selectors** |
| checks | `[[checks]]` | `when` fields match → must match `require` and have `off_peak_hours` a day in every season; `level` `error` refuses the contract, `warning` raises a `TariffWarning` and prices it as given |
| network schedule | `[network]` | seasons with peak/off-peak period names applied to the contract's off-peak hours; or year-round `peak`/`off_peak`; or a fixed `schedule` from `schedules.toml` |
| supply options | `[supply]` | a `field` naming the option, and `options.<name>` = `{ single = "base" }` or `{ peak = "HP", off_peak = "HC" }` |

`pack.contract(subscribed_kva=..., fields={...}, off_peak=..., seasonal_off_peak={...},
network=..., supply=...)` fills defaults, refuses unknown fields or values, and applies every
check. `pack.network_schedule(contract)` and `pack.supply_schedule(contract)` give the two
schedules; a contract's own `network` or `supply` schedule always wins.

The contract itself (`myenergy.domain.contract.Contract`) is generic: the pack's name, the
subscribed power, the fields, the off-peak hours (general and per season) and the optional
explicit schedules.

## Extending a pack

A pack with `extends = "fr-household"` inherits everything it does not redefine:

- tags and fields merge by name (a redefined field replaces the inherited one);
- `max_kva`, `network`, `supply` and `checks` are replaced when given (`checks = []` drops them);
- a **rate key** defined in its `rates/` hides the whole inherited history of that key;
  every other key is inherited (`LayeredRateSource`);
- a schedule of the same name hides the inherited one;
- the price books merge by line name, with `remove` (as a user's book on a pack's).

## Where packs come from (`myenergy.ports.packs.PackSource`)

`TomlPackSource` reads the built-in packs and every folder in `MYENERGY_PACK_ROOTS` (JSON list of
paths). Names are unique across folders (`[a-z0-9._-]`); a name used twice, an unknown or circular
`extends`, an oversized or malformed file are `DataFormatError`s naming the file. Rates are read
on first use and shared between a pack and the packs that extend it. A database-backed source (for
packs whose rates the M9 agent maintains) will implement the same port.

## The built-in `fr-household` pack

Tags `country = FR`, `sector = household`, `voltage = BT<=36kVA`, `source = official`. Fields
`segment`, `fta`, `status`, `contract`, `meter`, `supply_option`; the four TURPE time classes
(HPH/HCH, November–March; HPB/HCB, April–October) on the connection's off-peak hours; an error
check for the collective options and warning checks for the 8 off-peak hours; the rate tables of
the [Rates](rates.md) page.
