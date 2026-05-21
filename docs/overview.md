# civic-map-builder Overview

This repository collects civic association boundary contributions and renders
simple maps for review and publication.

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

## Optional Base Maps

Normal contribution review does not require OpenStreetMap data. Maintainers who
want base-map context can install the optional dependencies and prepare the local
cache:

```bash
pip install -e ".[dev,basemap]"
civic-map-builder basemap download maryland
civic-map-builder basemap extract
civic-map-builder render
```

`basemap download` stores a regional PBF in the platform-appropriate user cache.
District of Columbia is also available as `district-of-columbia`. `basemap
extract` creates a smaller project-local PBF for fast rendering and can set
`base_map.pbf_path` to that extract. `render` reads whichever PBF path is
configured. Re-running `basemap extract` uses the cached regional download when
`base_map.download` is set, not the currently selected generated extract.
Use `basemap use extract` to switch rendering back to the project extract or
`basemap use <download>` to switch to a regional cache; omitting the source
prompts with available choices. Advanced custom PBF paths remain a manual config
option. If `base_map.enabled` is true without a valid `pbf_path`, preview and
render commands fail with a configuration error.
