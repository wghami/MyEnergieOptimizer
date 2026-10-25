# MyEnergyOptimizer

Simulate a home or energy-community electricity system whose dispatch is decided by user-written logic rules, built on SmartMDAO.

- **Standards** every change must meet: [Engineering standards](standards/README.md).
- **API reference**, generated from the code: [Reference](reference.md).

## Architecture

- [Time and series](architecture/time-and-series.md): grids, quantities, resampling that conserves
  energy.
- [Profiles](architecture/profiles.md): shapes, sources, and the scalings that turn them into kW.
