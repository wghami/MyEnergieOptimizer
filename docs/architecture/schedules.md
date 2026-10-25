# Time-of-use schedules and the contract

Design: SPEC §3.1, ADR 0007, [M2](https://github.com/wghami/MyEnergyOptimizer/blob/main/planning/milestones/M2.md).
Notebook: [04 — Time-of-use schedules](../notebooks/04-time-of-use-schedules.ipynb).

## Schedules (`myenergy.domain.schedules`)

A `Schedule` splits time into **named periods**, any number of them. Each `PeriodRule` claims the
instants of one period:

| Part of a rule | Meaning | Left out |
|---|---|---|
| `windows` | daily wall-clock windows, written as on a bill (`TimeWindows.parse("2H00-7H00 12H30-15H30")`), may run past midnight | the whole day |
| `days` | labels from a `DayCalendar`: `mon` … `sun`, `weekday`, `weekend`, or others such as a Tempo colour | every day |
| `seasons` | names of the schedule's seasons (`Season.parse("winter", "11-01..03-31")`, any number, together covering each date once) | every season |

Whatever no rule claims goes to the season's `default`, else the schedule's `default`. Every
instant belongs to **exactly one** period: two rules claiming one instant, or an instant without a
period, are errors that name the instant. Rules are read **per instant**: a window is laid on every
local day and kept where the instant's own date has the rule's days and season.

`schedule.weights(grid, calendar)` gives `PeriodWeights`: the **share** of each step in each
period (rows sum to 1). Shares are fractions, so a step across a window edge is split by time and
`split(series)` gives kWh per period that add up to the total on any grid. They are computed in
UTC, so daylight-saving days need no special case (a window 02:00-07:00 lasts 4 real hours on the
spring day, 6 on the autumn day; a wall-clock time that does not exist is read with the offset in
force before the change, PEP 495).

`DayCalendar` is the hook for offers whose periods depend on announced days (Tempo, EJP): a data
source will provide a calendar that adds a colour label to each date. The default, `WEEKDAYS`,
gives weekday names.

### In TOML (`myenergy.adapters.tariffs.schedules`)

```toml
[schedules.ev-offer]
default = "peak"

[schedules.ev-offer.seasons]
winter = "11-01..03-31"
summer = { dates = "04-01..10-31", default = "summer-peak" }

[[schedules.ev-offer.periods]]
name = "super-off-peak"
windows = "02:00-06:00"

[[schedules.ev-offer.periods]]
name = "off-peak"
windows = "22:00-02:00 06:00-08:00"
days = ["sat", "sun"]
seasons = ["winter"]
```

`read_schedules(path)` returns every schedule of a file by name; files are size-limited and
schema-checked, and errors name the file and the schedule.

## The network's time classes (`myenergy.domain.time_classes`)

The French network tariff (TURPE) prices energy by HPH, HCH, HPB, HCB: off-peak or peak hours of
the high season (November–March) or the low season. `network_schedule(off_peak,
low_season_off_peak=None)` builds that schedule from a connection's off-peak hours, which may
differ between seasons. It is an ordinary `Schedule`; nothing else in the code depends on there
being four classes.

## Contract (`myenergy.domain.contract`)

| Field | Values | Used for |
|---|---|---|
| `subscribed_kva` | `0 < P ≤ 36` (Decimal) | power part of TURPE (b × P) |
| `supply_option` | `base`, `hp-hc` | the supplier schedule when `supply` is not given |
| `fta` | `CU`, `CU4`, `MU4`, `MUDT`, `LU`, `CU4-AC`, `MU4-AC` | network option |
| `off_peak`, `low_season_off_peak` | `TimeWindows` (the second only when seasons differ) | network schedule |
| `supply` | any `Schedule` | the supplier's own periods |
| `status` | `consumer`, `collective`, `producer-injection` | management component |
| `access_contract` | `supplier` (contrat unique), `user` (CARD) | management component |
| `meter` | `metered`, `unmetered` | metering component |

A contract carries **two schedules**: `network_schedule()` (the four classes on the connection's
off-peak hours) and `supply_schedule()` (`supply` when given; otherwise one period for `base`, or
`HP`/`HC` on the connection's off-peak hours for `hp-hc`).

Hard errors are kept for what cannot be priced: a power outside `(0, 36]` kVA, a collective option
without the collective status. A time-of-use contract with other than **8 off-peak hours a day**
(the TURPE norm) is accepted with a `TariffWarning` and priced as given.
