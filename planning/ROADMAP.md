# Roadmap

Scope and design: [SPEC.md](SPEC.md). Each milestone has a file in `milestones/`.

Every milestone ships the **notebooks** for the concepts it introduces (one concept per notebook,
DOC-12) and, where useful, **scripts** for specific or advanced uses (DOC-13). For M1, for example:
`01-time-grid`, `02-time-series-and-resampling`, `03-load-and-pv-profiles`, `04-tariffs`.

| Milestone | Goal | Status |
|---|---|---|
| M0 | Repository, tooling and standards in place; first release tagged | done (v0.1.0) |
| M1 | `TimeGrid`, `TimeSeries`, resampler; Enedis / CSV / synthetic profile sources; tariffs | planned |
| M2 | Physics, baseline policy, simulator, KPIs; energy-balance property tests | planned |
| M3 | Rules: vocabulary, `RuleSpec` → ASP compiler, sanitiser, `RulePolicy`, pre-run verifier | planned |
| M4 | FastAPI layer, jobs, result export | planned |
| M5 | Forecasters and forecast-aware rule facts; no-future-leak tests | planned |
| M6 | Oracle and MPC policies, scenario campaigns, energy-community topology; weather-API PV sources | planned |
| M7 | GUI (to be discussed) | planned |
| — | OpenSSF Best Practices badge (self-certification on bestpractices.dev; badge added once earned) | planned |
