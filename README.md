# civic-map-builder

A CLI tool to turn civic association boundary descriptions (bylaws, official text, etc.)
and contributor-supplied GeoJSON coordinates into reviewable boundary maps.

**Status:** early skeleton / work in progress.

## Setup

This project is intended to be run from a cloned git checkout, not installed as a
distributed package. The supported local workflow is a repo-local virtual
environment with an editable install, which installs dependencies, dev tools, and
the `civic-map-builder` command while keeping it pointed at the checked-out source.

```bash
git clone <repo-url>
cd civic-map-builder
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
civic-map-builder --help
civic-map-builder new example_association
civic-map-builder check example_association
civic-map-builder preview example_association
civic-map-builder render
civic-map-builder version
pytest
ruff check civic_map_builder tests
```

Each association contributes two files:

- `associations/<association_id>/boundary.md` for front matter plus the boundary
  bylaw or description snippet.
- `associations/<association_id>/boundary.geojson` for WGS84 lon/lat boundary
  coordinates.

Rendered PNGs are generated under `outputs/` and are not committed. Run commands
from the repository root so `civic-map-builder.project.yml` resolves as expected.
For workflow details, see `docs/overview.md`.
