# Scripts

Complete, runnable applications of the package for specific or advanced uses: the **second level**
of interaction, after the notebooks that explain one concept each. Each script is a command-line
program:

```bash
uv run python -m scripts.<name> --help
```

Every script (DOC-13):

- starts with a module docstring saying what it does and for whom;
- exposes `main(argv: Sequence[str] | None = None) -> int` and ends with
  `if __name__ == "__main__": raise SystemExit(main())`;
- uses only the public API of the package;
- has a smoke test `tests/scripts/test_<name>.py` that runs it on small inputs, including as
  `__main__`, so scripts count towards the 100 % coverage;
- is listed below, as `scripts/<name>.py`, with one line on what it is for.

## Scripts

_None yet._
