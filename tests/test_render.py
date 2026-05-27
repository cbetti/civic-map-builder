from __future__ import annotations

from pathlib import Path

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
    assert regional_path.stat().st_size > preview_path.stat().st_size
    assert not preview_path.with_suffix(".txt").exists()
    assert not regional_path.with_suffix(".txt").exists()


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
    assert (tmp_path / "outputs/maps/closeup.png").is_file()


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
        kwargs["output_path"].write_bytes(b"png")

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
        kwargs["output_path"].write_bytes(b"png")

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
    map_path.write_bytes(b"png")
    attribution_path.write_text(render.BASEMAP_ATTRIBUTION + "\n", encoding="utf8")
    monkeypatch.setattr(
        render,
        "render_regional_map",
        lambda **_kwargs: [map_path],
    )

    release_dir = render.stage_release_assets("2026-05.1", config_path=config_path)

    staged_attribution = release_dir / "regional-boundaries-2026-05.1.txt"
    assert staged_attribution.read_text(encoding="utf8") == render.BASEMAP_ATTRIBUTION + "\n"
    assert f"- Attribution: `{staged_attribution.name}`" in (
        release_dir / "README.md"
    ).read_text(encoding="utf8")


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


def _write_project_config(root: Path, *, extra_lines: list[str] | None = None) -> Path:
    extra_lines = extra_lines or []
    config_path = root / "config/project.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                'project_id: "test_project"',
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
