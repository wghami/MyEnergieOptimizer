# MyEnergieOptimizer

Simulate a home, and later an energy community, whose electricity dispatch is decided by
**logic rules the user writes**: who gets the solar energy first, when the battery charges, and
whether surplus is sold or stored. The rules run as [SmartMDAO](https://github.com/wghami/SmartMDAO)
rule disciplines, are verified before a run, and never see the future except through an explicit
forecast.

- Specification: [`planning/SPEC.md`](planning/SPEC.md) · Roadmap: [`planning/ROADMAP.md`](planning/ROADMAP.md)
- Engineering standards (binding): [`docs/standards/`](docs/standards/README.md)

## Development

```bash
uv sync
uv run pre-commit install
uv run pytest
```
