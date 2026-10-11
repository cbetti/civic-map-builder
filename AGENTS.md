# Repository Guidelines

## Project Structure & Module Organization
- CLI entrypoint: `civic_map_builder/cli.py` (Typer app). Subcommands delegate to focused modules such as `associations.py`, `basemap.py`, and `render.py`.
- Shared helpers: `civic_map_builder/util.py`; package metadata lives in `civic_map_builder/__init__.py`.
- Tests: `tests/` with smoke coverage for the CLI; add new module-level tests nearby.
- Docs: `README.md` for orientation, `CONTRIBUTING.md` for boundary contribution rules, and `docs/` for focused maintainer/rendering notes.
- Project and OSM source metadata config: `config/project.yml` and `config/osm_sources.yml`; machine-local render state lives in ignored `config/local.yml`.
- Example association data: `associations/sample__blair_highschool/` demonstrates boundary files, including a GeoJSON polygon with an interior exclusion/hole.

## Build, Test, and Development Commands
- Use uv for dependency management and all Python project commands; run commands from the repository root. `uv run` uses `.venv` without activation, including on Windows PowerShell.
- Install or refresh dev deps: `uv sync --extra dev`. The `dev` dependencies are an extra, not a dependency group. For basemap work, always sync both extras together with `uv sync --extra dev --extra basemap`; separate syncs can remove the previous extra.
- Run the CLI: `uv run civic-map-builder --help`, `uv run civic-map-builder check`, and `uv run civic-map-builder render` to verify command wiring.
- Optional OSM base maps: install `uv sync --extra dev --extra basemap`, then use `uv run civic-map-builder basemap --help`. Extraction also requires the external `osmium` CLI.
- After syncing, use plain `uv run` for all project commands; it retains installed extras by default. Do not repeat `--extra` on each run or use `uv run --exact`.
- Tests: `uv run pytest` (add `-q` for quieter output); coverage check with `uv run pytest --cov=civic_map_builder`.
- Lint/format: `uv run ruff check civic_map_builder tests` (line length 100 per `pyproject.toml`); run before PRs.

## Coding Style & Naming Conventions
- Python 3.10+, 4-space indentation, line length 100.
- Functions and modules use snake_case; classes in CapWords; CLI commands remain kebab-case as exposed by Typer.
- Prefer pure functions and small helpers in `util.py` when shared across subcommands.
- Keep CLI output concise and deterministic; return informative error messages rather than stack traces when possible.

## Testing Guidelines
- Use `pytest`; mirror module names in test files (e.g., `civic_map_builder/associations.py` → `tests/test_associations.py`).
- Cover new CLI options with argument parsing tests and one happy-path integration where feasible.
- Do not add permanent tests just to prove transitional cleanup or removed legacy behavior; verify that in-agent instead.
- Add minimal fixtures under `tests/`; update `associations/sample__blair_highschool/` only when intentionally changing documented sample data.

## Commit & Pull Request Guidelines
- Commits: short imperative subject (≤72 chars), keep related changes together, include rationale in body when non-obvious.
- PRs: describe intent, list commands run (tests/lint), link related issues, and include example CLI invocations or outputs when behavior changes.
- Keep diffs small; update docs in `docs/` when you add or change commands or data flow.

## Architecture Notes
- Typer drives the CLI; each subcommand delegates to domain modules that operate on YAML configs and geometry data.
- Geometry handling uses Shapely with WGS84 lon/lat GeoJSON input; rendering is Pillow-based and applies a local latitude aspect correction for map display.
- Optional OSM base-map rendering uses `osmium`, `requests`, and `platformdirs` from the `basemap` extra, plus the external `osmium` CLI for project extracts.
