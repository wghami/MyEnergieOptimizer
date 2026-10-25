# MyEnergyOptimizer

Simulate a home or energy-community electricity system whose dispatch is decided by user-written logic rules, built on SmartMDAO.

- **Standards** every change must meet: [Engineering standards](standards/README.md).
- **API reference**, generated from the code: [Reference](reference.md).

## Architecture

- [Time and series](architecture/time-and-series.md): grids, quantities, resampling that conserves
  energy.
- [Profiles](architecture/profiles.md): shapes, sources, and the scalings that turn them into kW.
- [Rates](architecture/rates.md): dated network tariffs and taxes, with their sources.
- [Schedules](architecture/schedules.md): user-defined time-of-use periods by window, day and
  season.
- [Tariff packs](architecture/packs.md): user-definable frameworks (fields, checks, schedules,
  rates); the French household pack is one of them.
- [Sites and energy flows](architecture/sites-and-flows.md): sites as data, asset kinds as
  plugins, and the import, export, self-consumed and shared energy that bills charge.
- [Price books](architecture/price-books.md): what a bill charges, as data: lines, bases,
  bundled or itemised network charges, and resolution against a contract.
- [Wiring](architecture/wiring.md): settings, plugins and the dependency-injection container.
