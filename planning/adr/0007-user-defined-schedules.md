# 0007 — Time-of-use periods are user-defined schedules; the network classes are one of them

Status: accepted (the network schedule and the contract moved into tariff packs, ADR 0008)
Date: 2026-10-25

## Context

The first version of time classes (M2 task 2) hard-wired the French network layout: four classes,
two seasons, one set of off-peak windows, exactly 8 off-peak hours (an error otherwise), and one
calendar shared by the network tariff and the supplier's prices. Real offers do not fit: no
off-peak at all, other than 8 hours, several windows, super-off-peak hours, weekend hours,
seasonal windows (TURPE 7 is moving towards summer afternoon off-peak hours), and day-colour
offers such as Tempo. The user asked that periods and seasons be easy to define freely, and that
nothing make the code rigid (another country should need minimal changes).

## Decision

- A domain `Schedule` names any number of periods. `PeriodRule`s claim instants by daily windows,
  day labels and seasons; seasons are user-defined date ranges covering the year once; defaults
  take what no rule claims, per season or overall.
- Every instant belongs to exactly one period: overlaps and gaps are errors naming the instant.
- Rules are evaluated **per instant** (the instant's local date decides its day and season).
- `weights(grid)` gives exact fractional shares per step, computed in UTC.
- Day labels come from a `DayCalendar` protocol (weekday names by default); colour calendars
  (Tempo, EJP) will be data sources implementing it.
- The TURPE four classes are a built-in schedule (`network_schedule`), with optional per-season
  off-peak hours.
- A contract carries two schedules: network and supply. The supply schedule may be any schedule.
- Regulated norms that do not prevent pricing (8 off-peak hours) are `TariffWarning`s, not errors.
- Schedules can be written in TOML (`adapters/tariffs/schedules.py`).

## Consequences

- New offers, and other countries' time-of-use structures, are data, not code.
- Price books (task 4) price **periods by name**, so they work with any schedule.
- Harder: errors can only be detected for the dates actually evaluated (a clash on red days shows
  when red days occur in the grid); per-instant rules surprise users who expect a night window to
  belong to the day it starts (documented, and shown in notebook 04).

## Alternatives considered

Priority-ordered rules (first match wins): easier to write, but silent shadowing hides mistakes.
Rules attached to the day a window starts: intuitive for nights, but the season of an instant
would then depend on the window, which contradicts how the network classifies energy.
