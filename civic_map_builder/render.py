from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .associations import Association, load_association, load_associations
from .basemap import BaseMapFeatures, configured_pbf_path, load_basemap_features
from .util import BaseMapConfig, CivicMapBuilderError, load_project_config


@dataclass(frozen=True)
class RenderStyle:
    width: int
    height: int
    padding: int
    fill: tuple[int, int, int]
    outline: tuple[int, int, int]
    background: tuple[int, int, int] = (255, 255, 255)
    context_fill: tuple[int, int, int] = (230, 230, 230)
    context_outline: tuple[int, int, int] = (170, 170, 170)


PREVIEW_STYLE = RenderStyle(
    width=1200,
    height=900,
    padding=70,
    fill=(76, 135, 211),
    outline=(24, 71, 137),
)
REGIONAL_STYLE = RenderStyle(
    width=3600,
    height=3000,
    padding=160,
    fill=(119, 172, 112),
    outline=(44, 98, 52),
)


def render_preview(association_id: str, *, config_path: Path | None = None) -> Path:
    config = load_project_config(path=config_path)
    selected = load_association(association_id, config_path=config_path)
    bounds = _padded_bounds(selected.geometry.bounds, config.base_map.padding_ratio)

    output_path = config.outputs.previews / f"{association_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _render_png(
        output_path=output_path,
        associations=[selected],
        style=PREVIEW_STYLE,
        selected_id=selected.association_id,
        bounds=bounds,
        base_features=_maybe_load_basemap(config.base_map, bounds),
    )
    return output_path


def render_regional_map(*, config_path: Path | None = None) -> list[Path]:
    config = load_project_config(path=config_path)
    associations = load_associations(config_path=config_path)
    if not associations:
        raise CivicMapBuilderError("No associations found to render.")

    default_bounds = _padded_bounds(
        _combined_bounds([association.geometry for association in associations]),
        config.base_map.padding_ratio,
    )
    render_targets = [("regional-boundaries", default_bounds)]
    render_targets.extend((view.name, view.bbox) for view in config.base_map.views)

    output_paths = []
    for name, bounds in render_targets:
        output_path = config.outputs.maps / f"{name}.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _render_png(
            output_path=output_path,
            associations=associations,
            style=REGIONAL_STYLE,
            selected_id=None,
            bounds=bounds,
            base_features=_maybe_load_basemap(config.base_map, bounds),
        )
        output_paths.append(output_path)
    return output_paths


def stage_release_assets(
    release_name: str | None = None,
    *,
    config_path: Path | None = None,
) -> Path:
    config = load_project_config(path=config_path)
    release_name = release_name or _default_release_name()
    map_paths = render_regional_map(config_path=config_path)

    release_dir = config.outputs.release / release_name
    release_dir.mkdir(parents=True, exist_ok=True)
    staged_maps = []
    for map_path in map_paths:
        staged_map = release_dir / f"{map_path.stem}-{release_name}.png"
        shutil.copyfile(map_path, staged_map)
        staged_maps.append(staged_map)
    (release_dir / "README.md").write_text(
        "\n".join(
            [
                f"# civic-map-builder {release_name}",
                "",
                "Generated release assets for manual upload to a GitHub Release.",
                "",
                *[f"- Map: `{staged_map.name}`" for staged_map in staged_maps],
                f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
                "",
            ]
        ),
        encoding="utf8",
    )
    return release_dir


def _render_png(
    *,
    output_path: Path,
    associations: list[Association],
    style: RenderStyle,
    selected_id: str | None,
    bounds: tuple[float, float, float, float],
    base_features: BaseMapFeatures | None,
) -> None:
    image = Image.new("RGB", (style.width, style.height), style.background)
    draw = ImageDraw.Draw(image)
    transform = _make_transform(bounds, style)
    if base_features is not None:
        _draw_basemap(draw, base_features, transform)

    for association in associations:
        if selected_id is not None and association.association_id == selected_id:
            continue
        _draw_geometry(
            draw,
            association.geometry,
            transform,
            fill=style.context_fill,
            outline=style.context_outline,
        )

    for association in associations:
        if selected_id is None or association.association_id == selected_id:
            _draw_geometry(
                draw,
                association.geometry,
                transform,
                fill=style.fill,
                outline=style.outline,
            )
            _draw_label(draw, association, transform, style)

    image.save(output_path, format="PNG")


def _draw_basemap(
    draw: ImageDraw.ImageDraw,
    features: BaseMapFeatures,
    transform,
) -> None:
    for geometry in features.water:
        _draw_area(draw, geometry, transform, fill=(209, 232, 244), outline=(164, 204, 225))
    for geometry in features.parks:
        _draw_area(draw, geometry, transform, fill=(222, 238, 214), outline=(184, 214, 168))
    for line in features.rail:
        _draw_line(draw, line, transform, fill=(100, 100, 100), width=2)
    for line, highway in features.roads:
        _draw_line(
            draw,
            line,
            transform,
            fill=(185, 185, 185),
            width=_road_width(highway),
        )


def _draw_area(
    draw: ImageDraw.ImageDraw,
    geometry: BaseGeometry,
    transform,
    *,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    for polygon in polygons:
        if isinstance(polygon, Polygon):
            exterior = [transform(x, y) for x, y in polygon.exterior.coords]
            draw.polygon(exterior, fill=fill, outline=outline)


def _draw_line(
    draw: ImageDraw.ImageDraw,
    line: LineString,
    transform,
    *,
    fill: tuple[int, int, int],
    width: int,
) -> None:
    points = [transform(x, y) for x, y in line.coords]
    if len(points) >= 2:
        draw.line(points, fill=fill, width=width, joint="curve")


def _road_width(highway: str) -> int:
    if highway in {"motorway", "trunk", "primary"}:
        return 5
    if highway in {"secondary", "tertiary"}:
        return 4
    if highway == "service":
        return 1
    return 2


def _draw_geometry(
    draw: ImageDraw.ImageDraw,
    geometry: BaseGeometry,
    transform,
    *,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    for polygon in polygons:
        if not isinstance(polygon, Polygon):
            continue
        exterior = [transform(x, y) for x, y in polygon.exterior.coords]
        draw.polygon(exterior, fill=fill, outline=outline)
        for interior in polygon.interiors:
            hole = [transform(x, y) for x, y in interior.coords]
            draw.polygon(hole, fill=(255, 255, 255), outline=outline)


def _draw_label(
    draw: ImageDraw.ImageDraw,
    association: Association,
    transform,
    style: RenderStyle,
) -> None:
    point = association.geometry.representative_point()
    x, y = transform(point.x, point.y)
    label = association.name
    draw.text((x + 8, y - 8), label, fill=(20, 20, 20))


def _make_transform(bounds: tuple[float, float, float, float], style: RenderStyle):
    minx, miny, maxx, maxy = bounds
    if minx == maxx or miny == maxy:
        raise CivicMapBuilderError("Cannot render geometry with zero-width bounds.")

    usable_width = style.width - (style.padding * 2)
    usable_height = style.height - (style.padding * 2)
    scale = min(usable_width / (maxx - minx), usable_height / (maxy - miny))
    x_offset = (style.width - ((maxx - minx) * scale)) / 2
    y_offset = (style.height - ((maxy - miny) * scale)) / 2

    def transform(x: float, y: float) -> tuple[float, float]:
        px = x_offset + ((x - minx) * scale)
        py = style.height - (y_offset + ((y - miny) * scale))
        return px, py

    return transform


def _combined_bounds(geometries: list[BaseGeometry]) -> tuple[float, float, float, float]:
    minx = min(geometry.bounds[0] for geometry in geometries)
    miny = min(geometry.bounds[1] for geometry in geometries)
    maxx = max(geometry.bounds[2] for geometry in geometries)
    maxy = max(geometry.bounds[3] for geometry in geometries)
    return minx, miny, maxx, maxy


def _padded_bounds(
    bounds: tuple[float, float, float, float],
    padding_ratio: float,
) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    if width == 0 or height == 0:
        return bounds
    x_padding = width * padding_ratio
    y_padding = height * padding_ratio
    return minx - x_padding, miny - y_padding, maxx + x_padding, maxy + y_padding


def _maybe_load_basemap(
    config: BaseMapConfig,
    bounds: tuple[float, float, float, float],
) -> BaseMapFeatures | None:
    if not config.enabled:
        return None
    return load_basemap_features(pbf_path=configured_pbf_path(config), bounds=bounds)


def _default_release_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m.1")
