# 0005 — Runtime dependencies for M1: numpy, pyarrow, pydantic, pydantic-settings, dishka

Status: accepted
Date: 2026-10-25

## Context

M1 introduces numerical time series, reads Enedis parquet files, validates configuration and wires
the first container (ADR 0002). DEP-1 requires one record per runtime dependency: why, licence,
maintenance.

## Decision

| Package | Why | Where it may be imported | Licence | Maintenance |
|---|---|---|---|---|
| numpy | arrays behind `TimeSeries`; vectorised resampling | domain and below (MEO-ARC-1 allows it) | BSD-3-Clause | NumFOCUS, very active |
| pyarrow | read Enedis parquet without pandas | `adapters` only | Apache-2.0 | Apache Arrow, very active |
| pydantic | validate configuration and, later, API payloads at the boundary | `adapters`, `api`, settings (MEO-PLG-3) | MIT | very active |
| pydantic-settings | `Settings` from environment and `.env` (SEC-7) | settings only | MIT | pydantic organisation |
| dishka | composition root (ADR 0002) | `bootstrap`, `api` | Apache-2.0 | active |

pandas is **not** used: pyarrow reads parquet directly, numpy holds the series, and leaving pandas
out keeps the dependency tree and the type surface smaller. The import contracts already forbid
pandas in the core.

## Consequences

- Five runtime dependencies, all OSI-licensed and compatible with MIT.
- Harder: some convenience of pandas time handling is reimplemented, small and tested: grids and
  overlap resampling.

## Alternatives considered

pandas for everything (heavier, looser typing, its own time-zone semantics in the core); polars
(fast, but a second dataframe model for little gain at this size).
