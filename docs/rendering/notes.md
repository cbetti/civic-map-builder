# Rendering Notes

These are the practical choices that moved the preview renderer closer to a
clean reference-map style.

- Use a local aspect-ratio correction for lon/lat rendering. Raw longitude and
  latitude degrees are not square pixels away from the equator; at North
  Woodside's latitude, using them directly stretched the map horizontally. The
  renderer now scales x distance by `cos(center_lat)` before fitting bounds to
  the image.
- Keep preview boundaries outline-only. A filled association polygon hides the
  streets and buildings that make the map readable. A dark navy stroke over a
  pale map is much closer to the target style.
- Add a subtle white halo under the boundary stroke. This keeps the boundary
  legible when it crosses roads, rail, and building outlines without making the
  line visually heavy.
- Draw more OSM context, especially building footprints. Roads alone make the
  map feel sparse; pale building outlines give neighborhood-scale context while
  staying unobtrusive.
- Use muted basemap colors: near-white building fills, light gray roads with
  white casing, soft green parks, and light rail. The base map should read as
  context, not compete with the boundary.
- Supersample previews and downsample with antialiasing. Rendering at 2x and
  resizing down gives cleaner diagonal roads and boundary edges.
- Crop previews tighter than the old default. Less padding makes the boundary
  feel intentional and closer to a reference-map export.

The progression images in this directory show the useful milestones, especially
the projection fix in `north_woodside_preview_iteration_05_local_projection.png`.
