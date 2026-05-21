# Repository Guidelines

## Project Structure & Module Organization
- CLI entrypoint: `civic_map_builder/cli.py` (Typer app). Subcommands typically call helpers in `civic_map_builder/*` (e.g., `ingest.py`, `validate.py`, `geometry_build.py`, `render.py`, `export.py`, `manage.py`).
- Shared helpers: `civic_map_builder/util.py`; package metadata lives in `civic_map_builder/__init__.py`.
- Tests: `tests/` with smoke coverage for the CLI; add new module-level tests nearby.
- Docs and design notes: `docs/` (overview, workflow reference, data sources, walkthroughs).
- Sample config/data: `data/base/` for fixtures used during development or examples.

## Build, Test, and Development Commands
- Create/activate venv (example): `python -m venv venv && source venv/bin/activate` (`.\venv\Scripts\activate` on Windows).
- Install dev deps: `pip install -e .[dev]`.
- Run the CLI: `civic-map-builder --help` and `civic-map-builder bylaws --help` to verify command wiring.
- Tests: `pytest` (add `-q` for quieter output); coverage check with `pytest --cov=civic_map_builder`.
- Lint/format: `ruff check civic_map_builder tests` (line length 100 per `pyproject.toml`); run before PRs.

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, line length 100.
- Functions and modules use snake_case; classes in CapWords; CLI commands remain kebab-case as exposed by Typer.
- Prefer pure functions and small helpers in `util.py` when shared across subcommands.
- Keep CLI output concise and deterministic; return informative error messages rather than stack traces when possible.

## Testing Guidelines
- Use `pytest`; mirror module names in test files (e.g., `civic_map_builder/ingest.py` → `tests/test_ingest.py`).
- Cover new CLI options with argument parsing tests and one happy-path integration where feasible.
- Add minimal fixtures under `tests/` (avoid modifying `data/base/` unless intended as documented sample data).

## Commit & Pull Request Guidelines
- Commits: short imperative subject (≤72 chars), keep related changes together, include rationale in body when non-obvious.
- PRs: describe intent, list commands run (tests/lint), link related issues, and include example CLI invocations or outputs when behavior changes.
- Keep diffs small; update docs in `docs/` when you add or change commands or data flow.

## Architecture Notes
- Typer drives the CLI; each subcommand delegates to domain modules that operate on YAML configs and geometry data.
- Geospatial stack uses GeoPandas/Shapely/pyproj; ensure CRS handling is explicit and validated when adding geometry logic.
