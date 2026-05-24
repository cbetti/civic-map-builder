# Contributing

This repo is both a civic-boundary dataset for the Montgomery County area and a
small CLI for checking and rendering that data.

## Add or update a boundary

1. Fork and clone the repo.
2. Create a branch.
3. Create/activate a venv (`python3 -m venv .venv`, `source .venv/bin/activate`; Windows PowerShell: `python -m venv .venv`, `.\.venv\Scripts\Activate.ps1`), then run `pip install -e ".[dev]"`.
4. Create a folder with `civic-map-builder new my_association`, or edit an
   existing folder under `associations/`.
5. Fill in `boundary.md` with the association name and a link to the source text.
6. Edit `boundary.geojson`.
7. Run:

   ```bash
   civic-map-builder check my_association
   civic-map-builder preview my_association
   ```

8. Open a pull request with the source link and any uncertainty noted.

## GeoJSON expectations

- Use WGS84 longitude/latitude coordinates: `[lon, lat]`.
- Use a single GeoJSON `Feature` with `Polygon` or `MultiPolygon` geometry.
- Polygon rings must be closed: the first and last coordinate are identical.
- To exclude an interior area, add it as an interior ring after the outer ring.
- See `associations/sample__blair_highschool/` for an example with a hole.
- Recommended editing tools: geojson.io for quick edits, QGIS for careful GIS
  work, and Mapshaper for cleanup/conversion.

## Source and data policy

- Use public or verifiable sources such as bylaws, official association pages,
  maps published by the association, or local government records.
- Cite the source by linking it in `boundary.md`; no separate citation file is
  needed.
- Approximate boundaries are acceptable when the source is descriptive, but note
  uncertainty in the pull request.
- Overlaps or disputed boundaries are reviewed by maintainers case by case.
- Prefer the clearest source text over guesswork. If two sources conflict,
  include both links and explain the conflict in the pull request.

## Code changes

- Run `ruff check civic_map_builder tests`.
- Run `pytest`.
- Keep CLI output concise and deterministic.
