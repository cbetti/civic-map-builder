from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .associations import Association, load_association, load_associations
from .util import CivicMapBuilderError, load_project_config


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

    output_path = config.outputs.previews / f"{association_id}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _render_png(
        output_path=output_path,
        associations=[selected],
        style=PREVIEW_STYLE,
        selected_id=selected.association_id,
        bounds=selected.geometry.bounds,
    )
    return output_path


def render_regional_map(*, config_path: Path | None = None) -> Path:
    config = load_project_config(path=config_path)
    associations = load_associations(config_path=config_path)
    if not associations:
        raise CivicMapBuilderError("No associations found to render.")

    output_path = config.outputs.maps / "regional-boundaries.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _render_png(
        output_path=output_path,
        associations=associations,
        style=REGIONAL_STYLE,
        selected_id=None,
        bounds=_combined_bounds([association.geometry for association in associations]),
    )
    return output_path


def stage_release_assets(
    release_name: str | None = None,
    *,
    config_path: Path | None = None,
) -> Path:
    config = load_project_config(path=config_path)
    release_name = release_name or _default_release_name()
    map_path = render_regional_map(config_path=config_path)

    release_dir = config.outputs.release / release_name
    release_dir.mkdir(parents=True, exist_ok=True)
    staged_map = release_dir / f"regional-boundaries-{release_name}.png"
    shutil.copyfile(map_path, staged_map)
    (release_dir / "README.md").write_text(
        "\n".join(
            [
                f"# civic-map-builder {release_name}",
                "",
                "Generated release assets for manual upload to a GitHub Release.",
                "",
                f"- Regional map: `{staged_map.name}`",
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
) -> None:
    image = Image.new("RGB", (style.width, style.height), style.background)
    draw = ImageDraw.Draw(image)
    transform = _make_transform(bounds, style)

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


def _default_release_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m.1")
