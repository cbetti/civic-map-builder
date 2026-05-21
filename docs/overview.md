# civic-map-builder Overview

This repository collects civic association boundary contributions and renders
simple boundary-only maps for review and publication.

## Contributor Workflow

1. Create or edit one association folder under `associations/<association_id>/`.
2. Add `boundary.md` with light YAML front matter (`name`, `bylaws_source_url`,
   `last_updated`, and `last_updated_by`) and the bylaw or boundary description
   snippet.
3. Add `boundary.geojson` with a GeoJSON `Feature` containing a `Polygon` or
   `MultiPolygon` in WGS84 lon/lat coordinates.
4. Run:

   ```bash
   civic-map-builder check <association_id>
   civic-map-builder preview <association_id>
   ```

5. Open a pull request with the two source files. Generated PNGs under `outputs/`
   are for local review and should not be committed.

The helper command `civic-map-builder new <association_id>` can create starter
files, but the files are plain text and may be created or edited manually.
The folder name is the association ID; contributors do not repeat it inside the
markdown or GeoJSON files.

## Maintainer Workflow

Review pull requests for clear source text, plausible coordinates, and any
warnings from `civic-map-builder check`. Boundary overlaps and disputed edges are
reported as warnings, not hard failures, because real civic boundaries can be
ambiguous.

When a new public map is useful, run:

```bash
civic-map-builder render
civic-map-builder release-assets --release-name YYYY-MM.N
```

Use date-based release names such as `2026-05.1` or `2026-05.2`, then upload the
generated PNG assets from `outputs/release/` to a GitHub Release.

## Future Base-Map Milestone

Version 1 intentionally does not require OpenStreetMap or any other base-map
data. A later milestone may add optional local base layers such as roads, parks,
county or ZIP boundaries, and labels. The earlier OSM ideas are preserved only as
future direction; contributors and maintainers should not need OSM data for the
initial workflow.
