# civic-map-builder

A CLI tool to turn civic association boundary descriptions (bylaws, official text, etc.)
and contributor-supplied GeoJSON coordinates into reviewable boundary maps.

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

## Base-Map Enhancement

The normal workflow renders faster boundary-only maps. To render with OSM context
behind the boundaries, install the optional dependencies, download a regional
PBF, create a smaller project extract, and render:

```bash
pip install -e ".[dev,basemap]"
civic-map-builder basemap download maryland
civic-map-builder basemap extract
civic-map-builder render
```

`basemap download` downloads one of the built-in regional OSM options, currently
`maryland` or `district-of-columbia`, into the platform cache. `basemap extract`
uses that configured regional PBF to create a much smaller project-local extract
for fast rendering, then asks whether to set `base_map.pbf_path` to the extract.
When `base_map.download` is set, later `basemap extract` runs continue to use the
cached regional download as the extraction source, even if rendering currently
points at a generated extract. `render` reads whichever `.osm.pbf` path is
configured. Switch render sources with `civic-map-builder basemap use extract`
or `civic-map-builder basemap use maryland`; omitting the source prompts with
the available project extract and regional downloads. Advanced custom PBF paths
can still be set manually in `civic-map-builder.project.yml`. OSM base-map data
is not committed.

Each association contributes two files:

- `associations/<association_id>/boundary.md` for front matter plus the boundary
  bylaw or description snippet.
- `associations/<association_id>/boundary.geojson` for WGS84 lon/lat boundary
  coordinates.

See `associations/sample__blair_highschool/` for a compact example, including a
GeoJSON polygon with an interior exclusion/hole.

Rendered PNGs are generated under `outputs/` and are not committed. Run commands
from the repository root so `civic-map-builder.project.yml` resolves as expected.
For workflow details, see `docs/overview.md`.
