# Contract and time classes

Design: SPEC §3.1, [M2](https://github.com/wghami/MyEnergyOptimizer/blob/main/planning/milestones/M2.md).
Notebook: [04 — Time classes](../notebooks/04-time-classes.ipynb).

## Contract (`myenergy.domain.contract`)

A `Contract` holds what the network tariff and the taxes depend on:

| Field | Values | Used for |
|---|---|---|
| `subscribed_kva` | `0 < P ≤ 36` (Decimal) | power part of TURPE (b × P) |
| `supply_option` | `base`, `hp-hc` | the supplier's prices |
| `fta` | `CU`, `CU4`, `MU4`, `MUDT`, `LU`, `CU4-AC`, `MU4-AC` | network option |
| `off_peak` | `OffPeakHours`, e.g. `OffPeakHours.parse("2H00-7H00 12H30-15H30")` | time classes |
| `status` | `consumer`, `collective`, `producer-injection` | management component |
| `access_contract` | `supplier` (contrat unique), `user` (CARD) | management component |
| `meter` | `metered`, `unmetered` | metering component |

It refuses what the tariff does not allow: a time-of-use network option or a peak/off-peak supply
option without exactly **8 off-peak hours a day**, a collective option (`-AC`) without the
collective status, a power outside `(0, 36]` kVA.

## Time classes (`myenergy.domain.time_classes`)

TURPE prices energy by four classes: HPH, HCH (peak and off-peak, high season, November–March),
HPB, HCB (low season, April–October). Off-peak hours are read on the **local wall clock**, seasons
follow the **local date**.

`TimeClassCalendar(off_peak).weights(grid)` returns `TimeClassWeights`: for every step, its
**share** in each class (rows sum to 1). Shares are fractions, not labels, so that a step that
straddles a window edge (a 60-minute step over 13:30) is split by time and energy per class stays
exact on any grid. `split(series)` turns a power or energy series into kWh per class; the four
values add up to the total.

```text
OffPeakHours + seasons ──► intervals in UTC ──► seconds of each step inside them ──► shares
                           (per local day)        (cumulative, like resampling)
```

Working in UTC makes daylight-saving days fall out naturally: a window 02:00–07:00 lasts 4 real
hours on the spring day and 6 on the autumn day. A wall-clock time that does not exist (02:30 on
the spring day) is read with the offset in force before the change (PEP 495). A property test
checks that shares partition every step and that shares on a fine grid average exactly to the
shares on a coarse one.
