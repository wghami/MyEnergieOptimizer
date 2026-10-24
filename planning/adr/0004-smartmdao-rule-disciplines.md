# 0004 — Dispatch logic runs as SmartMDAO rule disciplines

Status: accepted
Date: 2026-10-24

## Context

Users define *who gets the solar energy and when to sell* as logic. That logic must be reviewable,
deterministic, explainable when contradictory, and checked before a run.

## Decision

Rules compile to ASP and run as a SmartMDAO `RuleDiscipline`, fed by declared `Bands` (no floats
in ASP). Programs are sanitised (MEO-SEC-1), pinned (MEO-SIM-11) and verified over their finite
fact space before simulation (MEO-SIM-12). Quantities (kWh, EUR) stay in Python steps.

## Consequences

- Contradictory rules return a minimal `Conflict` instead of a wrong answer.
- Solving is memoised on the facts, so a year of steps costs as many solves as there are distinct
  situations.
- Harder: user-written ASP is untrusted code, so the sanitiser and the resource limits are
  mandatory.

## Alternatives considered

A hand-written rule engine (no infeasibility proofs, no SmartMDAO checks); a MILP for everything
(optimal, but not "logic the user writes", and planned separately as the MPC benchmark in M6).
