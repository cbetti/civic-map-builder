# civic-map-builder

A repo-local CLI and Montgomery County-area boundary dataset for turning civic
association source text and GeoJSON coordinates into reviewable PNG maps.

This repository is both a Python tool and a data project. Contributors can add or
improve boundaries under `associations/`; other groups can reuse the tool with
their own association data.

## Quick Start

```bash
git clone <repo-url>
cd civic-map-builder
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
civic-map-builder check
civic-map-builder render
```

Useful commands:

```bash
civic-map-builder new example_association
civic-map-builder check example_association
civic-map-builder preview example_association
civic-map-builder render
civic-map-builder release-assets --release-name YYYY-MM.N
pytest
ruff check civic_map_builder tests
```

## Boundary Data

Each association has one folder under `associations/` with:

- `boundary.md` for the association name, source link, and boundary text.
- `boundary.geojson` for WGS84 longitude/latitude boundary coordinates.

See `associations/sample__blair_highschool/` for an example, including a GeoJSON
polygon with an interior exclusion/hole. For contribution steps, GeoJSON
expectations, and source policy, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Optional Base Maps

Boundary-only rendering works without OpenStreetMap data. To render with OSM
context:

```bash
pip install -e ".[dev,basemap]"
civic-map-builder basemap download maryland
civic-map-builder basemap extract
civic-map-builder render
```

Download options live in `config/osm_downloads.yml`; project defaults live in
`config/project.yml`; machine-local base-map state lives in ignored
`config/local.yml`. Downloaded OSM data and generated PNGs are not committed.

## Maintainers

Run commands from the repository root so `config/project.yml` resolves correctly.
For publishing map assets, see [`docs/maintainer_release.md`](docs/maintainer_release.md).

## Licensing

This project uses a hybrid model to keep the tooling open and the data completely
unrestricted:

* **Software & Tooling:** All Python source code (`civic_map_builder/`), CLI scripts,
  configuration workflows, and tests are licensed under the **MIT License**. See the
  [LICENSE](LICENSE) file for details.
* **Geospatial Data:** All GeoJSON boundaries and metadata located within the
  `associations/` directory are dedicated to the public domain under the **Creative
  Commons Zero (CC0 1.0 Universal)** dedication. You are completely free to use, modify,
  and distribute this data without any legal restrictions or attribution requirements.

*Note: While credit is legally not required under CC0, we kindly request that you spread
the word or link back to this repository. This helps other local organizations discover
the project and contribute back to keep our regional data accurate!*

## Known Limitations

Cross-border base-map extracts work best when `basemap extract` can cut a
bounding box from one consolidated parent PBF; using two separate regional PBFs
currently requires manually merging matching-date files with `osmium merge`
before extraction. A future enhancement may automate that merge-then-extract
workflow for projects that span configured download regions.
