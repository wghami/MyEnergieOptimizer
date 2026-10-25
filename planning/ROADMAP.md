# Roadmap

Scope and design: [SPEC.md](SPEC.md). Each milestone has a file in `milestones/`.

Every milestone ships the **notebooks** for the concepts it introduces (one concept per notebook,
DOC-12) and, where useful, **scripts** for specific or advanced uses (DOC-13). For M1, for example:
`01-time-grid`, `02-time-series-and-resampling`, `03-load-and-pv-profiles`.

| Milestone | Goal | Status |
|---|---|---|
| M0 | Repository, tooling and standards in place; first release tagged | done (v0.1.0) |
| M1 | Time and profiles: `TimeGrid`, `TimeSeries`, resampling, scaling and calibration; Enedis / CSV / synthetic sources; first DI container ([M1](milestones/M1.md)) | done |
| M2 | Prices and bills: dated rate tables, energy flows, price books, itemised bills, inverse decomposition ([M2](milestones/M2.md)) | in progress (bill provided; design agreed 2026-10-25) |
| M3 | Physics, baseline policy, simulator, KPIs; energy-balance property tests | planned |
| M4 | Rules: vocabulary, `RuleSpec` → ASP compiler, sanitiser, `RulePolicy`, pre-run verifier | planned |
| M5 | FastAPI layer, jobs, result export | planned |
| M6 | Forecasters and forecast-aware rule facts; no-future-leak tests | planned |
| M7 | Oracle and MPC policies, scenario campaigns, energy-community topology and sales to neighbours; weather-API PV sources | planned |
| M8 | GUI (to be discussed) | planned |
| M9 | **Billing-data agent**, after the final code validation: an agent that fetches official prices and everything billing needs (TURPE grids, CTA, excise, VAT, regulated tariffs, feed-in prices), proposes rate-table updates with their source documents and effective dates, and leaves them `to verify` until a human confirms (SPEC decision 14). Everything it finds is **stored in a database** behind the `RateSource` port (ADR 0006), recoverable by its inputs (component, dates, kVA, option, FTA, status) | planned (requested 2026-10-25) |
| M10 | **Data curator**: automatic plausibility checks on every data source, run before data is used and reported, never silently repaired. First checks: solar production at night, gaps and duplicates, resolution changes, values far outside a profile's usual range, coefficients whose yearly mean drifts far from 1. Motivated by the Enedis `PRD3_BASE` anomaly at the 2024-10-04 resolution switch | planned (requested 2026-10-25) |
| — | **Metered data from Enedis** (index per HP/HC class or load curve for the user's meter): exact time classes for bills instead of estimated season splits (M2 decision 7) | planned (requested 2026-10-25) |
| — | OpenSSF Best Practices badge (self-certification on bestpractices.dev; badge added once earned) | planned |
