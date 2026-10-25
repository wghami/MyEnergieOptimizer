# 0009 — Sites are data, asset kinds are plugins, flows depend only on roles

Status: accepted
Date: 2026-10-25

## Context

M2 task 3 needs the energy flows that bills charge: import, export, self-consumption, and energy
shared with a sharing scheme. The user asked that adding households, EVs, PV or batteries be
transparent, with sources and sinks defined in TOML as for tariff packs. The SPEC planned assets
for M3; the flows need part of them now.

## Decision

- A **site** (one grid connection) is described in TOML: a contract under a tariff pack, assets
  by id and kind with their profile and options, and shares (direction, counterparty, measured
  profile).
- An **asset kind** is a plugin (`AssetKind`: name, role, `power()`), registered in the
  `myenergy.asset_kinds` entry-point group; built-ins `consumer` (sink) and `pv` (source). M3 adds
  `battery` (storage); other kinds come as needed.
- Flows know only **roles**: source, sink, storage. `SiteFlows` holds import, export,
  self-consumption and shared flows per counterparty, with derived supplied and sold; invariants
  are checked when it is built.
- Flows built from powers compare production and consumption per step of the requested grid; the
  bias of coarse steps is documented. Measured flows may hold import and export in one step.
- A pack may declare its sharing step (`sharing_step_minutes`); another step raises a warning.
- One meter per site: a separately metered EV charger is its own site; sub-metering for reporting
  can come later.

## Consequences

- A new household is a new site; a new kind of equipment is a plugin plus a line in a site file.
- The M3 flow graph will produce `SiteFlows`, so nothing here is replaced.
- Harder: which consumer used which PV kWh is not known until M3 (dispatch); allocation keys
  between sites wait for the community milestone, so shared flows are inputs for now.

## Alternatives considered

Hard-coded asset classes in the domain (the SPEC's first sketch): every new kind edits the core.
Flows from load and PV only: no place for EVs, batteries or several households.
