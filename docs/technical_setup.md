# Technical Setup

Use this guide for local development, validation, rendering, and basemap work.

## Quick start

Run commands from the repository root so `config/project.yml` resolves
correctly.

```bash
git clone <repo-url>
cd civic-map-builder
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
civic-map-builder check
civic-map-builder render
```

On Windows PowerShell, create and activate the virtual environment with:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Common commands

```bash
civic-map-builder new my_association
civic-map-builder check my_association
civic-map-builder preview my_association
civic-map-builder render
civic-map-builder release-assets --release-name YYYY-MM.N
pytest
ruff check civic_map_builder tests
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

To render with OSM context:

```bash
pip install -e ".[dev,basemap]"
civic-map-builder basemap download maryland
civic-map-builder basemap extract
civic-map-builder render
```

Rendering from a full OSM download is very slow.

`basemap extract` cuts that download down to this project's map area, which
makes repeated renders much faster.

OSM sources live in `config/osm_sources.yml`.

Project defaults live in `config/project.yml`.

Machine-local `render_basemap` state lives in ignored `config/local.yml`.

Downloaded OSM data and generated PNGs are not committed.

## Known limitation

Cross-border base-map extracts work best when `basemap extract` can cut a
bounding box from one consolidated parent PBF.

Using two separate regional PBFs currently requires manually merging
matching-date files with `osmium merge` before extraction.
