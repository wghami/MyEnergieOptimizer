# Enedis profile slices (test fixtures)

Two weeks (2024-09-28 22:00 UTC → 2024-10-12 22:00 UTC, i.e. Paris midnights) of the Enedis
*Coefficients des profils* for `RES1_BASE` (households, base option) and `PRD3_BASE` (solar
production). The window contains the switch from 30-minute to 15-minute values on
2024-10-04 22:00 UTC, so tests and notebooks exercise both resolutions.

- **Source:** Enedis, *Coefficients des profils*,
  [opendata.enedis.fr/datasets/coefficients-des-profils](https://opendata.enedis.fr/datasets/coefficients-des-profils),
  downloaded 2026-09 with the user's fetcher; columns kept: `timestamp`, `coefficient_ajuste`,
  `categorie`, `sous_profil`.
- **Licence:** [Licence Ouverte / Open Licence 2.0 (Etalab)](https://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf):
  reuse and redistribution allowed, with this attribution.

## Known anomaly (kept on purpose)

`PRD3_BASE` holds solar coefficients of about 4 between 2024-10-04 22:00 and 24:00 UTC (00:00 to
02:00 in Paris), exactly at the resolution switch. They match the same day's midday values, which
suggests a 12-hour shift in the stored rows (in the fetcher or in the published data; to be
checked). It is the only night with solar values above 0.5 in the whole 2021–2026 file. The reader
does not repair it; notebook 03 shows and explains it.
