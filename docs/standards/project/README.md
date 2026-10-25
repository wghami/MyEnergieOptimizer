# Project-specific standards — MyEnergyOptimizer

These rules **extend** the generic standards (01–11) and never weaken them. IDs are prefixed
`MEO-` so `standards check-standards` keeps every ID unique. This folder is owned by the project;
template updates never touch it.

| Document | Covers |
|---|---|
| [Architecture](architecture.md) | Layers, dependency injection with dishka, plugin registries |
| [Simulation](simulation.md) | Causality, decisions as policies, physical invariants, SmartMDAO usage |
| [Security](security.md) | Threat model: user-written logic programs, uploads, solver budgets, weather APIs |
