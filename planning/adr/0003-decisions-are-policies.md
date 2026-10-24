# 0003 — A decision is a policy for the step, never a setpoint

Status: accepted
Date: 2026-10-24

## Context

The controller must not know the future (MEO-SIM-1). At the start of a step it only knows the
past, plus a forecast if one is configured, while consumption and production *during* the step
are realised afterwards.

## Decision

A `Decision` states priorities, battery modes, sell or store, and whether grid charging is
allowed. `physics.settle` applies it to the **realised** values. The observation mode (`lagged` or
`ideal`) is a scenario switch (MEO-SIM-2).

## Consequences

- Energy balance holds by construction, whatever the forecast error; a wrong expectation shows up
  as cost, which is what we want to measure.
- Harder: a policy cannot express "charge exactly 1.3 kWh". If that becomes necessary (e.g. for
  MPC), it is expressed as caps inside the policy, not as setpoints.

## Alternatives considered

kWh setpoints per step: simpler to state, but a forecast error then has to be reconciled after the
fact, which hides where the cost came from.
