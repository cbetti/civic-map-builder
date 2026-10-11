# Technical Setup

Use this guide for local development, validation, rendering, and basemap work.

Use [uv](https://docs.astral.sh/uv/getting-started/installation/) to manage
Python dependencies and run project commands. Install uv before continuing.

## Quick start

Run commands from the repository root so `config/project.yml` resolves
correctly.

```bash
git clone <repo-url>
cd civic-map-builder
uv sync --extra dev
uv run civic-map-builder check
uv run civic-map-builder render
```

`uv sync` creates `.venv` and installs the project in editable mode along with
its dependencies. `uv run` uses that environment without requiring activation.
The same commands work in Windows PowerShell.

This project defines `dev` and `basemap` as optional dependency extras. Select
extras during setup or dependency refresh with `uv sync`, then use plain
`uv run` for daily commands. By default, `uv run` retains the installed extras;
you do not need to repeat `--extra` on each command.

For dependency refreshes, use `uv sync --extra dev` for boundary-only work or
`uv sync --extra dev --extra basemap` for basemap work. Always include all the
extras you want in the same sync command: separate syncs for `dev` and
`basemap` can remove the previously installed extra. Plain `uv sync` also
removes optional dependencies that are not otherwise needed. `uv run --exact`
can remove extras too, so use the plain `uv run` commands below.

## Common commands

```bash
uv run civic-map-builder new my_association
uv run civic-map-builder check my_association
uv run civic-map-builder preview my_association
uv run civic-map-builder render
uv run civic-map-builder release-assets --release-name YYYY-MM.N
uv run pytest
uv run ruff check civic_map_builder tests
```

## Boundary files

Each association has one folder under `associations/`.

`boundary.md` stores the association name, source link, and boundary notes.
The optional `association_contact` field names the association person engaged on
boundary review or clarification; leave it blank if no contact is known.

Use `boundary_confidence` in the front matter to summarize confidence in the
mapped boundary:

- `draft`: working placeholder, incomplete, or major unresolved uncertainty.
- `provisional`: usable and source-informed, but still has meaningful
  uncertainty or interpretation.
- `confirmed`: clear current source information with no known material
  ambiguity in the mapped boundary.

Use `known_overlaps` only for actual, intentional association overlaps. Both
affected association files must list each other by association id.

`boundary.geojson` stores WGS84 longitude/latitude boundary coordinates.

See `associations/sample__blair_highschool/` for a reference boundary with a
GeoJSON polygon and an interior exclusion.

## Optional basemaps

Boundary-only rendering works without OpenStreetMap data.

To render with OSM context, sync both extras together so the development tools
remain installed. Use this same sync command for future dependency refreshes:

```bash
uv sync --extra dev --extra basemap
uv run civic-map-builder basemap download maryland
uv run civic-map-builder basemap extract
uv run civic-map-builder render
```

Extraction also requires the external `osmium` CLI; uv installs the Python
bindings but does not install this system tool. Install `osmium-tool` with
`sudo apt install osmium-tool` on Debian/Ubuntu or `brew install osmium-tool`
on macOS. On Windows, use WSL or install osmium-tool manually.

Rendering from a full OSM download is very slow.

`basemap extract` cuts that download down to this project's map area, which
makes repeated renders much faster.

OSM sources live in `config/osm_sources.yml`.

Project defaults live in `config/project.yml`.

Machine-local `render_basemap` state lives in ignored `config/local.yml`.

Downloaded OSM data and generated PNGs are not committed.

`base_map.padding_ratio` controls visible map context around rendered
boundaries. `base_map.data_padding_ratio` controls the larger OSM data query
context used to avoid clipped large base-map features.

## Known limitation

Cross-border base-map extracts work best when `basemap extract` can cut a
bounding box from one consolidated parent PBF.

Using two separate regional PBFs currently requires manually merging
matching-date files with `osmium merge` before extraction.
