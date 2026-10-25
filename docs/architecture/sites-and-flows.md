# Sites and energy flows

Design: SPEC §3, ADR 0009, [M2](https://github.com/wghami/MyEnergyOptimizer/blob/main/planning/milestones/M2.md).
Notebook: [06 — Energy flows](../notebooks/06-energy-flows.ipynb).

## Sites are data (`myenergy.domain.sites`)

A `SiteSpec` is one grid connection: a contract under a [tariff pack](packs.md), **assets** by
id and **kind**, and the energy it **shares** with counterparties. Sites are written in TOML
(`myenergy.adapters.sites.toml_files`), several per file:

```toml
[sites.home]
pack = "fr-household"

[sites.home.contract]
subscribed_kva = 6
off_peak = "22:00-06:00"
fields = { fta = "CU4", supply_option = "hp-hc" }

[[sites.home.assets]]
id = "house"
kind = "consumer"
profile = { source = "synthetic", key = "household", annual_kwh = 3500 }

[[sites.home.assets]]
id = "roof"
kind = "pv"
profile = { source = "synthetic", key = "pv-clear-sky", peak_kwp = 3, yield_kwh_per_kwp = 1100 }

[[sites.home.shares]]
direction = "in"
counterparty = "street-operation"
profile = { source = "meter", key = "allocated", as_measured = true }
```

A profile names its source and key, an optional `time_shift_minutes`, and exactly one scaling:
`annual_kwh`, `peak_kwp` with `yield_kwh_per_kwp`, or `as_measured = true`. The contract may name
a `supply_schedule` shipped by its pack.

## Asset kinds are plugins (`myenergy.ports.assets`)

An `AssetKind` has a `name`, a **role** (`source`, `sink` or `storage`) and `power(asset, grid,
profiles)` returning kW on the grid: non-negative for a source or a sink, signed for storage
(positive when it returns energy). Kinds register as entry points of `myenergy.asset_kinds`,
built-ins included: `consumer` (sink) and `pv` (source) read the asset's profile. A battery, an
EV or a heat pump is another kind; a household is another site. Neither changes the flow or bill
code.

## Flows (`myenergy.domain.flows`)

`SiteResolver.flows(site, grid)` signs each asset's power by role and builds `SiteFlows`, kWh
series on the grid:

| Flow | Meaning |
|---|---|
| `import` / `export` | what the meter records drawing from / injecting into the network |
| `self_consumption` | production used on site, never seen by the meter |
| `shared_in` / `shared_out` | the parts of import / export allocated by a sharing scheme to or from a counterparty |
| `supplied` = import - shared_in | what the supplier sells |
| `sold` = export - shared_out | what goes to the grid buyer |

Invariants: no flow is negative; shared energy never exceeds import or export (the error names the
step); one counterparty per direction; everything on one grid. Flows built from asset powers never
import and export in the same step; `SiteFlows.measured(...)` accepts meter data where a step holds
both, because the meter saw it.

**The step matters.** Production and consumption are compared per step, so coarse steps hide
moments when the site both imported and exported: they show more self-consumption than really
happens (in notebook 06, about 19 % more at 60 minutes than at 5 minutes on a bursty day). The net
energy (import minus export) does not change. A pack may declare the step at which its sharing
schemes allocate energy (`sharing_step_minutes`); computing a sharing site on another step raises a
`TariffWarning`.

## Later

The physical flow graph of the simulator (M3: who sends energy to whom, battery included) will
produce these meter flows; sharing keys between sites come with the community milestone.
