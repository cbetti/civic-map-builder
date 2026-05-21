# Design Proposal: Community Boundary Contributions

`civic-map-builder` is a repo-local CLI for a community-maintained boundary data
repository. Civic association contributors provide boundary source text and
GeoJSON coordinates, while trusted maintainers review pull requests and publish
generated map images as release assets.

## Canonical Data

Each association owns one folder:

```text
associations/<association_id>/
  boundary.md
  boundary.geojson
```

`boundary.md` starts with light YAML front matter:

```markdown
---
name: Example Civic Association
bylaws_source_url:
last_updated: YYYY-MM-DD
last_updated_by: TODO Name
---

Paste the bylaw or authoritative boundary-description snippet here.
Example: is bounded on the East by Main St, on the South by the CSX tracks, on the West
by Pine Ave, and on the North by Vale Grove Park.
```

`boundary.geojson` is a GeoJSON `Feature` whose geometry is a `Polygon` or
`MultiPolygon` in WGS84 lon/lat coordinates. The folder name is the canonical
association ID; contributors do not need to repeat it inside either file.

## CLI

The public CLI uses direct verbs:

- `civic-map-builder new <association_id>` creates starter text files.
- `civic-map-builder check [association_id]` validates one association or all.
- `civic-map-builder preview <association_id>` renders a focused PNG preview.
- `civic-map-builder render` renders the full regional PNG map.
- `civic-map-builder release-assets [--release-name YYYY-MM.N]` stages files for
  manual GitHub Release upload.

Checks fail on user errors that should block a pull request: missing paired
files, bad markdown front matter, malformed GeoJSON, invalid polygon geometry,
non-lon/lat coordinate ranges, or invalid folder names. Checks warn on maintainer
concerns such as overlaps or suspicious boundary size.

## Rendering

Version 1 renders boundary-only PNG files for broad browser compatibility:

- `outputs/previews/<association_id>.png`
- `outputs/maps/regional-boundaries.png`
- `outputs/release/<release-name>/...`

Generated outputs are not committed. Release names are date-based and lightweight,
for example `2026-05.1`.

## Future Base Maps

The old OSM/base-map concept is deferred. A later milestone may add optional local
base layers for roads, parks, county or ZIP boundaries, labels, or other neutral
context. Version 1 should not require contributors or maintainers to download or
prepare OSM data.
