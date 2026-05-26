from __future__ import annotations

import math
import shutil
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

from .associations import Association, load_association, load_associations
from .basemap import BaseMapFeatures, configured_render_basemap, load_basemap_features
from .util import BaseMapConfig, CivicMapBuilderError, load_project_config

BASEMAP_ATTRIBUTION = (
    "Map data: OpenStreetMap contributors (ODbL 1.0). "
    "Regional extracts from Geofabrik."
)


@dataclass(frozen=True)
class RenderStyle:
    width: int
    height: int
    padding: int
    fill: tuple[int, int, int] | None
    outline: tuple[int, int, int]
    outline_width: int = 1
    outline_halo: tuple[int, int, int] | None = None
    outline_halo_width: int = 0
    fill_opacity: int = 255
    color_by_association: bool = False
    background: tuple[int, int, int] = (255, 255, 255)
    context_fill: tuple[int, int, int] = (230, 230, 230)
    context_outline: tuple[int, int, int] = (170, 170, 170)
    show_labels: bool = True
    label_size: int = 20
    render_scale: int = 1


PREVIEW_STYLE = RenderStyle(
    width=1200,
    height=900,
    padding=45,
    fill=None,
    outline=(28, 32, 88),
    outline_width=2,
    outline_halo=(255, 255, 255),
    outline_halo_width=4,
    fill_opacity=28,
    color_by_association=True,
    background=(250, 250, 250),
    show_labels=False,
    render_scale=2,
)
REGIONAL_STYLE = RenderStyle(
    width=3600,
    height=3000,
    padding=160,
    fill=None,
    outline=(44, 98, 52),
    fill_opacity=70,
    color_by_association=True,
    label_size=40,
)

POLYGON_PALETTE = (
    (83, 137, 214),
    (105, 169, 104),
    (219, 141, 74),
    (151, 111, 195),
    (213, 104, 125),
    (71, 166, 174),
    (188, 157, 61),
    (121, 145, 205),
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


def render_regional_map(
    *,
    config_path: Path | None = None,
    include_samples: bool = True,
) -> list[Path]:
    config = load_project_config(path=config_path)
    associations = load_associations(config_path=config_path, include_samples=include_samples)
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
    include_samples: bool = False,
) -> Path:
    config = load_project_config(path=config_path)
    release_name = release_name or _default_release_name()
    map_paths = render_regional_map(config_path=config_path, include_samples=include_samples)

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
    pixel_scale = style.render_scale
    draw_style = _scaled_style(style, pixel_scale)
    image = Image.new("RGBA", (draw_style.width, draw_style.height), (*style.background, 255))
    draw = ImageDraw.Draw(image)
    transform = _make_transform(bounds, draw_style)
    if base_features is not None:
        _draw_basemap(draw, base_features, transform, pixel_scale=pixel_scale)

    for index, association in enumerate(associations):
        if selected_id is not None and association.association_id == selected_id:
            continue
        fill = _association_fill(association, index, style)
        _draw_geometry(
            image,
            draw,
            association.geometry,
            transform,
            fill=fill,
            outline=style.context_outline,
            width=pixel_scale,
            fill_opacity=max(18, style.fill_opacity // 2),
        )

    for index, association in enumerate(associations):
        if selected_id is None or association.association_id == selected_id:
            fill = _association_fill(association, index, style)
            outline = _association_outline(fill) if style.color_by_association else style.outline
            _draw_geometry(
                image,
                draw,
                association.geometry,
                transform,
                fill=fill,
                outline=outline,
                width=draw_style.outline_width,
                halo=style.outline_halo,
                halo_width=draw_style.outline_halo_width,
                fill_opacity=style.fill_opacity,
            )
            if style.show_labels:
                _draw_label(draw, association, transform, draw_style)

    if pixel_scale > 1:
        image = image.resize((style.width, style.height), Image.Resampling.LANCZOS)
    image.convert("RGB").save(output_path, format="PNG")
    _write_attribution(output_path, base_features=base_features)


def _write_attribution(output_path: Path, *, base_features: BaseMapFeatures | None) -> None:
    attribution_path = output_path.with_suffix(".txt")
    if base_features is None:
        if attribution_path.exists():
            attribution_path.unlink()
        return
    attribution_path.write_text(BASEMAP_ATTRIBUTION + "\n", encoding="utf8")


def _scaled_style(style: RenderStyle, pixel_scale: int) -> RenderStyle:
    if pixel_scale == 1:
        return style
    return RenderStyle(
        width=style.width * pixel_scale,
        height=style.height * pixel_scale,
        padding=style.padding * pixel_scale,
        fill=style.fill,
        outline=style.outline,
        outline_width=style.outline_width * pixel_scale,
        outline_halo=style.outline_halo,
        outline_halo_width=style.outline_halo_width * pixel_scale,
        fill_opacity=style.fill_opacity,
        color_by_association=style.color_by_association,
        background=style.background,
        context_fill=style.context_fill,
        context_outline=style.context_outline,
        show_labels=style.show_labels,
        label_size=style.label_size * pixel_scale,
        render_scale=1,
    )


def _draw_basemap(
    draw: ImageDraw.ImageDraw,
    features: BaseMapFeatures,
    transform,
    *,
    pixel_scale: int,
) -> None:
    for geometry in features.water:
        _draw_area(draw, geometry, transform, fill=(209, 232, 244), outline=(164, 204, 225))
    for geometry in features.parks:
        _draw_area(draw, geometry, transform, fill=(226, 239, 219), outline=(190, 216, 181))
    for geometry in features.buildings:
        _draw_area(draw, geometry, transform, fill=(247, 247, 247), outline=(216, 216, 216))
    for line in features.rail:
        _draw_line(draw, line, transform, fill=(176, 176, 176), width=2 * pixel_scale)
    for line, highway in features.roads:
        road_width = _road_width(highway) * pixel_scale
        _draw_line(
            draw,
            line,
            transform,
            fill=(255, 255, 255),
            width=road_width + (2 * pixel_scale),
        )
        _draw_line(
            draw,
            line,
            transform,
            fill=_road_color(highway),
            width=road_width,
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
        return 7
    if highway in {"secondary", "tertiary"}:
        return 5
    if highway == "service":
        return 2
    return 3


def _road_color(highway: str) -> tuple[int, int, int]:
    if highway in {"motorway", "trunk", "primary"}:
        return 198, 198, 198
    if highway in {"secondary", "tertiary"}:
        return 210, 210, 210
    return 220, 220, 220


def _association_fill(
    association: Association,
    index: int,
    style: RenderStyle,
) -> tuple[int, int, int] | None:
    if not style.color_by_association:
        return style.fill
    palette_index = (zlib.crc32(association.association_id.encode("utf8")) + index) % len(
        POLYGON_PALETTE
    )
    return POLYGON_PALETTE[palette_index]


def _association_outline(fill: tuple[int, int, int] | None) -> tuple[int, int, int]:
    if fill is None:
        return 28, 32, 88
    return tuple(max(35, int(channel * 0.42)) for channel in fill)


def _draw_geometry(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    geometry: BaseGeometry,
    transform,
    *,
    fill: tuple[int, int, int] | None,
    outline: tuple[int, int, int],
    width: int = 1,
    halo: tuple[int, int, int] | None = None,
    halo_width: int = 0,
    fill_opacity: int = 255,
) -> None:
    polygons = geometry.geoms if isinstance(geometry, MultiPolygon) else [geometry]
    for polygon in polygons:
        if not isinstance(polygon, Polygon):
            continue
        exterior = [transform(x, y) for x, y in polygon.exterior.coords]
        if fill is not None:
            _draw_transparent_polygon(image, exterior, fill, fill_opacity)
        if halo is not None and halo_width > width:
            draw.line(exterior, fill=halo, width=halo_width, joint="curve")
        draw.line(exterior, fill=outline, width=width, joint="curve")
        for interior in polygon.interiors:
            hole = [transform(x, y) for x, y in interior.coords]
            draw.polygon(hole, fill=(255, 255, 255))
            if halo is not None and halo_width > width:
                draw.line(hole, fill=halo, width=halo_width, joint="curve")
            draw.line(hole, fill=outline, width=width, joint="curve")


def _draw_transparent_polygon(
    image: Image.Image,
    exterior: list[tuple[float, float]],
    fill: tuple[int, int, int],
    opacity: int,
) -> None:
    overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.polygon(exterior, fill=(*fill, opacity))
    image.alpha_composite(overlay)


def _draw_label(
    draw: ImageDraw.ImageDraw,
    association: Association,
    transform,
    style: RenderStyle,
) -> None:
    point = association.geometry.representative_point()
    x, y = transform(point.x, point.y)
    label = association.name
    font = _label_font(style.label_size)
    max_width = _label_max_width(association.geometry, transform)
    lines = _wrap_label(draw, label, font, max_width)
    line_boxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_heights = [box[3] - box[1] for box in line_boxes]
    line_spacing = max(4, style.label_size // 5)
    text_height = sum(line_heights) + (line_spacing * (len(lines) - 1))
    text_y = y - (text_height / 2)
    cursor_y = text_y
    for line, box, line_height in zip(lines, line_boxes, line_heights):
        line_width = box[2] - box[0]
        draw.text((x - (line_width / 2), cursor_y), line, fill=(20, 20, 20), font=font)
        cursor_y += line_height + line_spacing


def _label_max_width(geometry: BaseGeometry, transform) -> int:
    minx, _miny, maxx, _maxy = geometry.bounds
    left, _ = transform(minx, _miny)
    right, _ = transform(maxx, _maxy)
    return max(120, int(abs(right - left) * 0.72))


def _wrap_label(
    draw: ImageDraw.ImageDraw,
    label: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    words = label.split()
    if not words:
        return [label]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if _text_width(draw, candidate, font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _label_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def _make_transform(bounds: tuple[float, float, float, float], style: RenderStyle):
    minx, miny, maxx, maxy = bounds
    if minx == maxx or miny == maxy:
        raise CivicMapBuilderError("Cannot render geometry with zero-width bounds.")
    center_lat = (miny + maxy) / 2
    x_scale = math.cos(math.radians(center_lat))
    projected_width = (maxx - minx) * x_scale
    projected_height = maxy - miny

    usable_width = style.width - (style.padding * 2)
    usable_height = style.height - (style.padding * 2)
    scale = min(usable_width / projected_width, usable_height / projected_height)
    x_offset = (style.width - (projected_width * scale)) / 2
    y_offset = (style.height - (projected_height * scale)) / 2

    def transform(x: float, y: float) -> tuple[float, float]:
        px = x_offset + ((x - minx) * x_scale * scale)
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
    return load_basemap_features(pbf_path=configured_render_basemap(config), bounds=bounds)


def _default_release_name() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m.1")
