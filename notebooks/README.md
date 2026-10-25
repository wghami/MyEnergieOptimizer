# Notebooks

**One concept per notebook, and one notebook per concept.** Each one shows what happens under the
hood, step by step, with the real package. Read them in order: each builds on the previous one.

Every notebook (DOC-12):

- is named `NN-concept.ipynb` (`01-…`, `02-…`, without gaps);
- opens with a markdown cell `# NN — <concept>`, stating the **Concept:** and what
  **You will learn:**, and closes with a markdown cell saying what comes **Next:**;
- uses only the public API of the package;
- is committed **executed**, top to bottom in a fresh kernel, so GitHub and the documentation
  site show the results without running anything:
  `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/NN-concept.ipynb`;
- is executed again by the `notebooks` hook and in CI, so a notebook that no longer runs fails
  the push.

## Notebooks

1. [01 — Time grid](01-time-grid.ipynb): UTC ranges of equal steps, daylight-saving days, and why
   invalid grids are refused.
2. [02 — Time series and resampling](02-time-series-and-resampling.ipynb): quantities, power vs
   energy, and resampling that conserves energy.
3. [03 — Load and PV profiles](03-load-and-pv-profiles.ipynb): Enedis shapes across the resolution
   switch, the scalings that turn shapes into kW, synthetic and measured profiles.
4. [04 — Time-of-use schedules](04-time-of-use-schedules.ipynb): user-defined periods by window,
   day and season, exact shares per step, daylight-saving days, and a contract's network and
   supply schedules.
5. [05 — Tariff packs](05-tariff-packs.ipynb): what a pack holds, how a contract is checked, a
   research pack that changes one tax, and a pack for somewhere else.
