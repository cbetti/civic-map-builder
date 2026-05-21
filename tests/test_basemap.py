from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from civic_map_builder.basemap import (
    available_downloads,
    extract_basemap,
    extraction_bbox,
    extraction_source_path,
    format_bbox,
    prepare_basemap,
    pbf_cache_path,
    project_extract_path,
    update_base_map_config,
)
from civic_map_builder.util import CivicMapBuilderError, ProjectConfig
import pytest
from shapely.geometry import box


def test_base_map_config_parses_named_views(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: true",
            "  download: maryland",
            "  pbf_path: cache/maryland-latest.osm.pbf",
            "  padding_ratio: 0.2",
            "  views:",
            "    county:",
            "      bbox: [-77.2, 38.8, -76.8, 39.2]",
        ],
    )

    config = ProjectConfig.load(config_path)

    assert config.base_map.enabled is True
    assert config.base_map.download == "maryland"
    assert config.base_map.pbf_path == (tmp_path / "cache/maryland-latest.osm.pbf").resolve()
    assert config.base_map.padding_ratio == 0.2
    assert config.base_map.views[0].name == "county"
    assert config.base_map.views[0].bbox == (-77.2, 38.8, -76.8, 39.2)


def test_pbf_cache_path_uses_download_option_and_cache_root(tmp_path: Path) -> None:
    path = pbf_cache_path("maryland", cache_root=tmp_path / "cache")

    assert path == tmp_path / "cache/osm/geofabrik/maryland-latest.osm.pbf"


def test_district_of_columbia_is_available_download(tmp_path: Path) -> None:
    path = pbf_cache_path("district-of-columbia", cache_root=tmp_path / "cache")

    assert "district-of-columbia" in available_downloads()
    assert path == tmp_path / "cache/osm/geofabrik/district-of-columbia-latest.osm.pbf"


def test_project_extract_path_uses_project_id_and_cache_root(tmp_path: Path) -> None:
    path = project_extract_path("test_project", cache_root=tmp_path / "cache")

    assert path == tmp_path / "cache/osm/extracts/test_project-basemap.osm.pbf"


def test_extraction_bbox_uses_association_bounds_plus_padding() -> None:
    associations = [
        SimpleNamespace(geometry=box(-77.0, 39.0, -76.99, 39.01)),
        SimpleNamespace(geometry=box(-77.02, 38.99, -77.01, 39.0)),
    ]

    bounds = extraction_bbox(associations, 0.1)

    assert bounds == pytest.approx((-77.023, 38.988, -76.987, 39.012))
    assert format_bbox(bounds) == "-77.023,38.988,-76.987,39.012"


def test_prepare_basemap_reuses_cached_file_without_progress(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  download: maryland",
        ],
    )
    cache_root = tmp_path / "cache"
    cached_path = pbf_cache_path("maryland", cache_root=cache_root)
    cached_path.parent.mkdir(parents=True)
    cached_path.write_bytes(b"cached")
    progress_calls = []

    prepared = prepare_basemap(
        config_path=config_path,
        cache_root=cache_root,
        progress=lambda received, total: progress_calls.append((received, total)),
    )

    assert prepared.path == cached_path
    assert prepared.downloaded is False
    assert progress_calls == []


def test_extract_basemap_missing_osmium_has_install_hints(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            f"  pbf_path: {tmp_path / 'maryland-latest.osm.pbf'}",
        ],
    )
    (tmp_path / "maryland-latest.osm.pbf").write_bytes(b"pbf")
    _write_association(tmp_path, "alpha", -77.0, 39.0)
    monkeypatch.setattr("civic_map_builder.basemap.shutil.which", lambda _name: None)

    with pytest.raises(CivicMapBuilderError) as exc_info:
        extract_basemap(config_path=config_path, cache_root=tmp_path / "cache")

    message = str(exc_info.value)
    assert "osmium" in message
    assert "sudo apt install osmium-tool" in message
    assert "brew install osmium-tool" in message


def test_extract_basemap_runs_expected_osmium_command(monkeypatch, tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            f"  pbf_path: {tmp_path / 'maryland-latest.osm.pbf'}",
            "  padding_ratio: 0.25",
        ],
    )
    input_path = tmp_path / "maryland-latest.osm.pbf"
    input_path.write_bytes(b"pbf")
    _write_association(tmp_path, "alpha", -77.0, 39.0, size=0.004)
    monkeypatch.setattr("civic_map_builder.basemap.shutil.which", lambda _name: "osmium")
    expected_output = tmp_path / "cache/osm/extracts/test_project-basemap.osm.pbf"
    calls = []

    def fake_runner(command, check):
        expected_output.write_bytes(b"extract")
        calls.append((command, check))

    extracted = extract_basemap(
        config_path=config_path,
        cache_root=tmp_path / "cache",
        command_runner=fake_runner,
    )

    assert extracted.output_path == expected_output
    assert calls == [
        (
            [
                "osmium",
                "extract",
                "--bbox",
                "-77.001,38.999,-76.995,39.005",
                str(input_path),
                "-o",
                str(expected_output),
                "--overwrite",
            ],
            True,
        )
    ]


def test_extract_basemap_prefers_download_cache_over_existing_extract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cache_root = tmp_path / "cache"
    regional_path = pbf_cache_path("maryland", cache_root=cache_root)
    regional_path.parent.mkdir(parents=True)
    regional_path.write_bytes(b"regional pbf")
    existing_extract = project_extract_path("old_project", cache_root=cache_root)
    existing_extract.parent.mkdir(parents=True, exist_ok=True)
    existing_extract.write_bytes(b"old extract")
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  download: maryland",
            f"  pbf_path: {existing_extract}",
        ],
    )
    expected_output = project_extract_path("test_project", cache_root=cache_root)
    _write_association(tmp_path, "alpha", -77.0, 39.0, size=0.004)
    monkeypatch.setattr("civic_map_builder.basemap.shutil.which", lambda _name: "osmium")
    calls = []

    def fake_runner(command, check):
        expected_output.write_bytes(b"extract")
        calls.append((command, check))

    extracted = extract_basemap(
        config_path=config_path,
        cache_root=cache_root,
        command_runner=fake_runner,
    )

    assert extracted.input_path == regional_path
    assert calls[0][0][4] == str(regional_path)


def test_extraction_source_rejects_extract_without_download(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    existing_extract = project_extract_path("test_project", cache_root=cache_root)
    existing_extract.parent.mkdir(parents=True)
    existing_extract.write_bytes(b"extract")
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            f"  pbf_path: {existing_extract}",
        ],
    )
    config = ProjectConfig.load(config_path)

    with pytest.raises(CivicMapBuilderError) as exc_info:
        extraction_source_path(config, cache_root=cache_root)

    assert "generated project extract" in str(exc_info.value)


def test_update_base_map_config_sets_download_and_pbf_path(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    pbf_path = tmp_path / "cache/osm/geofabrik/maryland-latest.osm.pbf"

    update_base_map_config(
        config_path=config_path,
        enabled=True,
        download="maryland",
        pbf_path=pbf_path,
    )
    config = ProjectConfig.load(config_path)

    assert config.base_map.enabled is True
    assert config.base_map.download == "maryland"
    assert config.base_map.pbf_path == pbf_path


def _write_project_config(root: Path, *, extra_lines: list[str] | None = None) -> Path:
    extra_lines = extra_lines or []
    config_path = root / "civic-map-builder.project.yml"
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


def _write_association(
    root: Path,
    association_id: str,
    lon: float,
    lat: float,
    *,
    size: float = 0.004,
) -> None:
    directory = root / "associations" / association_id
    directory.mkdir(parents=True)
    (directory / "boundary.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {association_id.title()} Association",
                "---",
                "",
                "A concise boundary description.",
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
      [{lon + size}, {lat}],
      [{lon + size}, {lat + size}],
      [{lon}, {lat + size}],
      [{lon}, {lat}]
    ]]
  }}
}}
""",
        encoding="utf8",
    )
