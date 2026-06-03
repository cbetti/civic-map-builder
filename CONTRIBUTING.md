# Contributing

This project depends on local knowledge.

If an association boundary is missing, unclear, or wrong, please help improve
it.

You do not need to be technical to contribute.

## Option 1: Send boundary information

This is the best path for most associations.

Please send whatever you have: an association name, website, bylaws, map image,
PDF, marked-up screenshot, street description, uncertainty note, or boundary data
from a mapping tool.

GeoJSON copied from geojson.io or geojson.io/next is helpful if you have it, but
plain descriptions are also useful.

It is okay if the boundary is approximate. Please identify the source and call
out anything uncertain.

Useful examples:

- "Our northern boundary is Dennis Avenue."
- "We include both sides of X Street from A Avenue to B Avenue."
- "This map is from our 2024 membership flyer."
- "The east edge is unclear because our old bylaws conflict with the website."

## Option 2: Submit a GitHub pull request

Technical contributors can add or update boundaries directly.

1. Fork and clone the repo.
2. Create a branch.
3. Create and activate a Python virtual environment.
4. Install dev dependencies with `pip install -e ".[dev]"`.
5. Create a folder with `civic-map-builder new my_association`, or edit an
   existing folder under `associations/`.
6. Fill in `boundary.md` with the association name, source link, and notes.
7. Edit `boundary.geojson`.
8. Run:

   ```bash
   civic-map-builder check my_association
   civic-map-builder preview my_association
   ```

9. Open a pull request with the source link and any uncertainty noted.

## Boundary source policy

Use public or verifiable sources when possible, such as bylaws, official
association pages, maps published by the association, local government records,
or other public documents.

Approximate boundaries are acceptable when the source is descriptive.

If two sources conflict, include both and explain the conflict.

Overlaps or disputed boundaries will be reviewed case by case.

## GeoJSON expectations

For technical contributors:

- Use WGS84 longitude/latitude coordinates: `[lon, lat]`.
- Use a single GeoJSON `Feature` with `Polygon` or `MultiPolygon` geometry.
- Polygon rings must be closed.
- To exclude an interior area, add it as an interior ring after the outer ring.
- See `associations/sample__blair_highschool/` for a reference boundary with a
  hole.
- Recommended editing tools include geojson.io, geojson.io/next, QGIS, and
  Mapshaper.

## Code changes

For changes to the CLI or rendering code:

```bash
ruff check civic_map_builder tests
pytest
```
