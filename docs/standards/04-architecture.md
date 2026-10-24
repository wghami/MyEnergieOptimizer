# 04 — Architecture

Projects use **ports and adapters** (hexagonal architecture). The domain is pure; everything that
touches the outside world (files, network, frameworks, solvers, clocks) sits behind a port
(`Protocol`). Only the composition root sees concrete classes. Each project declares its layers in
`.importlinter` and describes them in `docs/standards/project/`.

| ID | Rule | Enforced by |
|---|---|---|
| ARC-1 | The domain imports only the standard library and pure computational libraries. No I/O, clock, logging side effects or framework. | `import-contracts` hook (import-linter `forbidden` contract) |
| ARC-2 | Layers depend downwards only. Siblings that must stay independent are declared independent. | `import-contracts` hook (`layers` / `independence` contracts) |
| ARC-3 | Adapters implement ports and never import application services or the API layer. | `import-contracts` hook |
| ARC-4 | Only the composition root imports concrete adapters. | `import-contracts` hook |
| ARC-5 | Production code never imports test libraries. | `import-contracts` hook (template contract) |
| ARC-6 | No import cycles. | import-linter, ruff `TID` |
| PRT-1 | Every external capability is a port with a **contract test suite** that every implementation, including test fakes, must pass. | `tests/contract/`, review |
| PRT-2 | Extension points (registries, plugins) are tested by adding a test-only implementation **without editing** existing modules. | architecture tests |
