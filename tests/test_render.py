from __future__ import annotations

import math
from pathlib import Path

import pytest
from PIL import Image
from shapely.geometry import LineString, Polygon

from civic_map_builder.basemap import BaseMapFeatures
from civic_map_builder import render
from civic_map_builder.util import CivicMapBuilderError


def test_render_outputs_nontrivial_pngs(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    _write_association(tmp_path, "beta", "Beta Association", -77.02, 39.0)

    preview_path = render.render_preview("alpha", config_path=config_path)
    regional_paths = render.render_regional_map(config_path=config_path)
    regional_path = regional_paths[0]

    assert preview_path.is_file()
    assert regional_path.is_file()
    assert preview_path.stat().st_size > 1_000
    assert not preview_path.with_suffix(".txt").exists()
    assert not regional_path.with_suffix(".txt").exists()

    expected_bounds = (-77.03, 39.0, -77.016, 39.004)
    with Image.open(regional_path) as image:
        assert image.size == _expected_regional_dimensions(_padded_bounds(expected_bounds, 0.05))


def test_render_writes_named_view_pngs(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: false",
            "  views:",
            "    closeup:",
            "      bbox: [-77.04, 38.99, -77.00, 39.02]",
        ],
    )
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)

    regional_paths = render.render_regional_map(config_path=config_path)

    assert [path.name for path in regional_paths] == [
        "regional-boundaries.png",
        "closeup.png",
    ]
    closeup_path = tmp_path / "outputs/maps/closeup.png"
    assert closeup_path.is_file()
    with Image.open(closeup_path) as image:
        assert image.size == _expected_regional_dimensions(
            _padded_bounds((-77.04, 38.99, -77.00, 39.02), 0.05)
        )


def test_preview_output_scale_changes_final_image_dimensions(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)

    preview_path = render.render_preview("alpha", config_path=config_path, output_scale=3)

    with Image.open(preview_path) as image:
        assert image.size == _expected_preview_dimensions(
            _padded_bounds((-77.03, 39.0, -77.026, 39.004), 0.05),
            height=2700,
        )


def test_preview_renders_without_outer_pixel_frame_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    rendered_styles: list[render.RenderStyle] = []

    def fake_render_png(**kwargs) -> None:
        rendered_styles.append(kwargs["style"])
        kwargs["output_path"].write_bytes(b"png")

    monkeypatch.setattr(render, "_render_png", fake_render_png)

    render.render_preview("alpha", config_path=config_path, output_scale=2)

    assert rendered_styles[0].padding == 0
    assert rendered_styles[0].width == _expected_preview_dimensions(
        _padded_bounds((-77.03, 39.0, -77.026, 39.004), 0.05),
        height=1800,
    )[0]
    assert rendered_styles[0].height == 1800


def test_preview_can_render_with_outer_pixel_frame(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    rendered_styles: list[render.RenderStyle] = []

    def fake_render_png(**kwargs) -> None:
        rendered_styles.append(kwargs["style"])
        kwargs["output_path"].write_bytes(b"png")

    monkeypatch.setattr(render, "_render_png", fake_render_png)

    render.render_preview("alpha", config_path=config_path, include_frame=True)

    assert rendered_styles[0].padding == render.PREVIEW_STYLE.padding


def test_preview_uses_context_bounds_for_basemap_and_image(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: true",
            f"  render_basemap: {tmp_path / 'basemap.osm.pbf'}",
            "  padding_ratio: 0.05",
            "  data_padding_ratio: 0.15",
        ],
    )
    (tmp_path / "basemap.osm.pbf").write_bytes(b"pbf")
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    loaded_bounds: list[tuple[float, float, float, float]] = []

    def fake_load_basemap_features(**kwargs):
        loaded_bounds.append(kwargs["bounds"])
        return None

    monkeypatch.setattr(render, "load_basemap_features", fake_load_basemap_features)

    render.render_preview("alpha", config_path=config_path, include_frame=False)

    assert loaded_bounds[0] == pytest.approx(
        (-77.0306, 38.9994, -77.0254, 39.0046)
    )


def test_regional_render_uses_context_bounds_for_basemap_and_image(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: true",
            f"  render_basemap: {tmp_path / 'basemap.osm.pbf'}",
            "  padding_ratio: 0.05",
            "  data_padding_ratio: 0.15",
        ],
    )
    (tmp_path / "basemap.osm.pbf").write_bytes(b"pbf")
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    loaded_bounds: list[tuple[float, float, float, float]] = []

    def fake_load_basemap_features(**kwargs):
        loaded_bounds.append(kwargs["bounds"])
        return None

    monkeypatch.setattr(render, "load_basemap_features", fake_load_basemap_features)

    regional_path = render.render_regional_map(config_path=config_path)[0]

    assert loaded_bounds[0] == pytest.approx(
        (-77.0306, 38.9994, -77.0254, 39.0046)
    )
    with Image.open(regional_path) as image:
        assert image.size == _expected_regional_dimensions(
            _padded_bounds((-77.03, 39.0, -77.026, 39.004), 0.05)
        )


def test_preview_output_scale_must_be_in_supported_range(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)

    try:
        render.render_preview("alpha", config_path=config_path, output_scale=5)
    except CivicMapBuilderError as exc:
        assert "between 1 and 4" in str(exc)
    else:
        raise AssertionError("Expected invalid preview scale to fail")


def test_render_regional_map_includes_sample_associations_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    _write_association(tmp_path, "sample__demo", "Sample Demo", -77.02, 39.0)
    rendered_ids: list[list[str]] = []

    def fake_render_png(**kwargs) -> None:
        rendered_ids.append(
            [association.association_id for association in kwargs["associations"]]
        )
        _write_blank_png(kwargs["output_path"])

    monkeypatch.setattr(render, "_render_png", fake_render_png)

    render.render_regional_map(config_path=config_path)
    render.render_regional_map(config_path=config_path, include_samples=False)

    assert rendered_ids == [
        ["alpha", "sample__demo"],
        ["alpha"],
    ]


def test_release_assets_excludes_sample_associations_by_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    _write_association(tmp_path, "sample__demo", "Sample Demo", -77.02, 39.0)
    rendered_ids: list[list[str]] = []

    def fake_render_png(**kwargs) -> None:
        rendered_ids.append(
            [association.association_id for association in kwargs["associations"]]
        )
        _write_blank_png(kwargs["output_path"])

    monkeypatch.setattr(render, "_render_png", fake_render_png)

    render.stage_release_assets("2026-05.1", config_path=config_path)
    render.stage_release_assets("2026-05.2", config_path=config_path, include_samples=True)

    assert rendered_ids == [
        ["alpha"],
        ["alpha", "sample__demo"],
    ]


def test_release_assets_stages_attribution_sidecars(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_project_config(tmp_path)
    map_path = tmp_path / "outputs/maps/regional-boundaries.png"
    attribution_path = map_path.with_suffix(".txt")
    map_path.parent.mkdir(parents=True)
    _write_blank_png(map_path)
    attribution_path.write_text(render.BASEMAP_ATTRIBUTION + "\n", encoding="utf8")
    monkeypatch.setattr(
        render,
        "render_regional_map",
        lambda **_kwargs: [map_path],
    )

    release_dir = render.stage_release_assets("2026-05.1", config_path=config_path)

    staged_attribution = release_dir / "test-project-2026-05.1.txt"
    attribution_lines = staged_attribution.read_text(encoding="utf8").splitlines()
    assert attribution_lines[:4] == [
        render.BASEMAP_ATTRIBUTION,
        "",
        "- Map: test-project-2026-05.1.png",
        "- Attribution: test-project-2026-05.1.txt",
    ]
    assert attribution_lines[4].startswith("- Generated at: ")
    assert len(attribution_lines) == 5


def test_release_assets_uses_public_project_slug(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        project_id="montgomery_county_area_associations",
    )
    map_path = tmp_path / "outputs/maps/regional-boundaries.png"
    attribution_path = map_path.with_suffix(".txt")
    map_path.parent.mkdir(parents=True)
    _write_blank_png(map_path)
    attribution_path.write_text(render.BASEMAP_ATTRIBUTION + "\n", encoding="utf8")
    monkeypatch.setattr(render, "render_regional_map", lambda **_kwargs: [map_path])

    release_dir = render.stage_release_assets("2026-05.1", config_path=config_path)

    assert (release_dir / "montgomery-county-area-associations-2026-05.1.png").is_file()
    assert (release_dir / "montgomery-county-area-associations-2026-05.1.txt").is_file()


def test_release_assets_prefixes_named_views_with_public_project_slug(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        project_id="montgomery_county_area_associations",
    )
    default_map = tmp_path / "outputs/maps/regional-boundaries.png"
    view_map = tmp_path / "outputs/maps/north-hills.png"
    default_map.parent.mkdir(parents=True)
    _write_blank_png(default_map)
    _write_blank_png(view_map)
    monkeypatch.setattr(
        render,
        "render_regional_map",
        lambda **_kwargs: [default_map, view_map],
    )

    release_dir = render.stage_release_assets("2026-05.1", config_path=config_path)

    assert (release_dir / "montgomery-county-area-associations-2026-05.1.png").is_file()
    assert (
        release_dir / "montgomery-county-area-associations-north-hills-2026-05.1.png"
    ).is_file()
    attribution_text = (
        release_dir / "montgomery-county-area-associations-2026-05.1.txt"
    ).read_text(encoding="utf8")
    assert "- Map: montgomery-county-area-associations-2026-05.1.png" in attribution_text
    assert (
        "- Map: montgomery-county-area-associations-north-hills-2026-05.1.png"
        in attribution_text
    )
    assert not (
        release_dir / "montgomery-county-area-associations-north-hills-2026-05.1.txt"
    ).exists()


def test_release_footer_text_uses_repository_project_and_release() -> None:
    assert render._release_footer_text(
        "montgomery-county-area-associations",
        "2026-06.1",
    ) == (
        "github.com/cbetti/civic-map-builder | "
        "montgomery-county-area-associations | 2026-06.1"
    )


def test_render_can_draw_synthetic_basemap_features(tmp_path: Path, monkeypatch) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    features = BaseMapFeatures(
        roads=[(LineString([(-77.031, 39.001), (-77.025, 39.004)]), "residential")],
        rail=[LineString([(-77.031, 39.003), (-77.025, 39.001)])],
        water=[Polygon([(-77.031, 39.0), (-77.029, 39.0), (-77.029, 39.002), (-77.031, 39.0)])],
        parks=[Polygon([(-77.028, 39.002), (-77.026, 39.002), (-77.026, 39.004), (-77.028, 39.002)])],
    )
    monkeypatch.setattr(render, "_maybe_load_basemap", lambda _config, _bounds: features)

    preview_path = render.render_preview("alpha", config_path=config_path)

    assert preview_path.is_file()
    assert preview_path.stat().st_size > 1_000
    attribution_path = preview_path.with_suffix(".txt")
    assert attribution_path.read_text(encoding="utf8") == (
        "Map data: OpenStreetMap contributors (ODbL 1.0). "
        "Regional extracts from Geofabrik.\n"
    )


def test_enabled_basemap_requires_configured_render_basemap(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: true",
        ],
    )
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)

    try:
        render.render_preview("alpha", config_path=config_path)
    except CivicMapBuilderError as exc:
        assert "base_map.render_basemap is not configured" in str(exc)
    else:
        raise AssertionError("Expected missing render_basemap to fail")


def _write_project_config(
    root: Path,
    *,
    project_id: str = "test_project",
    extra_lines: list[str] | None = None,
) -> Path:
    extra_lines = extra_lines or []
    config_path = root / "config/project.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                f'project_id: "{project_id}"',
                'associations_dir: "associations"',
                "outputs:",
                '  previews: "outputs/previews"',
                '  maps: "outputs/maps"',
                '  release: "outputs/release"',
                *extra_lines,
                "",
            ]
        ),
        encoding="utf8",
    )
    return config_path


def _write_blank_png(path: Path, *, size: tuple[int, int] = (900, 700)) -> None:
    Image.new("RGB", size, (255, 255, 255)).save(path, format="PNG")


def _expected_regional_dimensions(
    bounds: tuple[float, float, float, float],
) -> tuple[int, int]:
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2
    projected_width = (maxx - minx) * math.cos(math.radians(center_lat))
    projected_height = maxy - miny
    return (
        round(projected_width * render.REGIONAL_PIXELS_PER_DEGREE),
        round(projected_height * render.REGIONAL_PIXELS_PER_DEGREE),
    )


def _padded_bounds(
    bounds: tuple[float, float, float, float],
    padding_ratio: float,
) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    x_padding = (maxx - minx) * padding_ratio
    y_padding = (maxy - miny) * padding_ratio
    return minx - x_padding, miny - y_padding, maxx + x_padding, maxy + y_padding


def _expected_preview_dimensions(
    bounds: tuple[float, float, float, float],
    *,
    height: int,
) -> tuple[int, int]:
    minx, miny, maxx, maxy = bounds
    center_lat = (miny + maxy) / 2
    aspect = ((maxx - minx) * math.cos(math.radians(center_lat))) / (maxy - miny)
    return round(height * aspect), height


def _write_association(root: Path, association_id: str, name: str, lon: float, lat: float) -> None:
    directory = root / "associations" / association_id
    directory.mkdir(parents=True)
    (directory / "boundary.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "---",
                "",
                "Boundary text.",
                "",
            ]
        ),
        encoding="utf8",
    )
    (directory / "boundary.geojson").write_text(
        f"""{{
  "type": "Feature",
  "properties": {{}},
  "geometry": {{
    "type": "Polygon",
    "coordinates": [[
      [{lon}, {lat}],
      [{lon + 0.004}, {lat}],
      [{lon + 0.004}, {lat + 0.004}],
      [{lon}, {lat + 0.004}],
      [{lon}, {lat}]
    ]]
  }}
}}
""",
        encoding="utf8",
    )
