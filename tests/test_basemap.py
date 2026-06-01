from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from civic_map_builder.basemap import (
    _osm_sources,
    available_osm_sources,
    extract_basemap,
    extraction_bbox,
    extraction_source_path,
    format_bbox,
    prepare_basemap,
    pbf_cache_path,
    project_extract_path,
    update_base_map_config,
)
from civic_map_builder.util import DEFAULT_LOCAL_CONFIG, CivicMapBuilderError, ProjectConfig
import pytest
from shapely.geometry import box


def test_base_map_config_parses_named_views(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: true",
            "  osm_source: maryland",
            "  render_basemap: cache/maryland-latest.osm.pbf",
            "  padding_ratio: 0.2",
            "  views:",
            "    county:",
            "      bbox: [-77.2, 38.8, -76.8, 39.2]",
        ],
    )

    config = ProjectConfig.load(config_path)

    assert config.base_map.enabled is True
    assert config.base_map.osm_source == "maryland"
    assert config.base_map.render_basemap == (tmp_path / "cache/maryland-latest.osm.pbf").resolve()
    assert config.base_map.padding_ratio == 0.2
    assert config.base_map.views[0].name == "county"
    assert config.base_map.views[0].bbox == (-77.2, 38.8, -76.8, 39.2)


@pytest.mark.parametrize("view_name", ["North Hills", "north_hills", "north/hills"])
def test_base_map_config_rejects_unsafe_view_names(
    tmp_path: Path,
    view_name: str,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  views:",
            f"    {view_name}:",
            "      bbox: [-77.2, 38.8, -76.8, 39.2]",
        ],
    )

    with pytest.raises(CivicMapBuilderError) as exc_info:
        ProjectConfig.load(config_path)

    assert "'base_map.views' names must be lowercase kebab-case filename slugs" in str(
        exc_info.value
    )


def test_project_config_load_applies_only_local_base_map_runtime_keys(
    monkeypatch,
    tmp_path: Path,
) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  enabled: false",
            "  osm_source: maryland",
            "  padding_ratio: 0.15",
            "  views: {}",
        ],
    )
    local_pbf = tmp_path / "cache/extract.osm.pbf"
    (tmp_path / DEFAULT_LOCAL_CONFIG).write_text(
        "\n".join(
            [
                "base_map:",
                "  enabled: true",
                "  osm_source: district-of-columbia",
                f"  render_basemap: {local_pbf}",
                "  padding_ratio: 0.8",
                "  views:",
                "    local:",
                "      bbox: [-78, 38, -77, 39]",
                "",
            ]
        ),
        encoding="utf8",
    )
    monkeypatch.chdir(tmp_path)

    merged = ProjectConfig.load()
    explicit = ProjectConfig.load(config_path)

    assert merged.base_map.enabled is True
    assert merged.base_map.osm_source == "district-of-columbia"
    assert merged.base_map.render_basemap == local_pbf
    assert merged.base_map.padding_ratio == 0.15
    assert merged.base_map.views == ()
    assert explicit.base_map.enabled is False
    assert explicit.base_map.render_basemap is None


def test_project_config_allows_base_map_without_default_osm_source(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  padding_ratio: 0.15",
            "  views: {}",
        ],
    )

    config = ProjectConfig.load(config_path)

    assert config.base_map.osm_source is None
    assert config.base_map.render_basemap is None


def test_project_config_rejects_old_base_map_key_names(tmp_path: Path) -> None:
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  download: maryland",
            "  pbf_path: cache/maryland-latest.osm.pbf",
        ],
    )

    with pytest.raises(CivicMapBuilderError) as exc_info:
        ProjectConfig.load(config_path)

    assert "base_map.download" in str(exc_info.value)
    assert "base_map.osm_source" in str(exc_info.value)


def test_local_config_rejects_old_base_map_key_names(monkeypatch, tmp_path: Path) -> None:
    _write_project_config(tmp_path)
    (tmp_path / DEFAULT_LOCAL_CONFIG).write_text(
        "\n".join(
            [
                "base_map:",
                "  enabled: true",
                "  pbf_path: cache/maryland-latest.osm.pbf",
                "",
            ]
        ),
        encoding="utf8",
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(CivicMapBuilderError) as exc_info:
        ProjectConfig.load()

    assert "base_map.pbf_path" in str(exc_info.value)
    assert "base_map.render_basemap" in str(exc_info.value)


def test_pbf_cache_path_uses_osm_source_and_cache_root(tmp_path: Path) -> None:
    path = pbf_cache_path("maryland", cache_root=tmp_path / "cache")

    assert path == tmp_path / "cache/osm/geofabrik/maryland-latest.osm.pbf"


def test_district_of_columbia_is_available_osm_source(tmp_path: Path) -> None:
    path = pbf_cache_path("district-of-columbia", cache_root=tmp_path / "cache")

    assert "district-of-columbia" in available_osm_sources()
    assert path == tmp_path / "cache/osm/geofabrik/district-of-columbia-latest.osm.pbf"


def test_osm_source_config_loads_options_from_yaml(tmp_path: Path) -> None:
    config_path = _write_osm_sources_config(
        tmp_path,
        [
            "osm_sources:",
            "  custom-region:",
            "    label: Custom Region",
            "    source_url: https://example.test/custom.osm.pbf",
            "    filename: custom.osm.pbf",
        ],
    )

    options = _osm_sources(config_path)

    assert options["custom-region"].label == "Custom Region"
    assert options["custom-region"].source_url == "https://example.test/custom.osm.pbf"
    assert options["custom-region"].filename == "custom.osm.pbf"


def test_osm_source_config_requires_source_mapping(tmp_path: Path) -> None:
    config_path = _write_osm_sources_config(tmp_path, ["osm_sources: []"])

    with pytest.raises(CivicMapBuilderError) as exc_info:
        _osm_sources(config_path)

    assert "'osm_sources' must be a mapping" in str(exc_info.value)


def test_osm_source_config_requires_fields(tmp_path: Path) -> None:
    config_path = _write_osm_sources_config(
        tmp_path,
        [
            "osm_sources:",
            "  custom-region:",
            "    label: Custom Region",
            "    filename: custom.osm.pbf",
        ],
    )

    with pytest.raises(CivicMapBuilderError) as exc_info:
        _osm_sources(config_path)

    assert "osm_sources.custom-region.source_url" in str(exc_info.value)


def test_osm_source_config_rejects_path_filename(tmp_path: Path) -> None:
    config_path = _write_osm_sources_config(
        tmp_path,
        [
            "osm_sources:",
            "  custom-region:",
            "    label: Custom Region",
            "    source_url: https://example.test/custom.osm.pbf",
            "    filename: nested/custom.osm.pbf",
        ],
    )

    with pytest.raises(CivicMapBuilderError) as exc_info:
        _osm_sources(config_path)

    assert "must be a filename" in str(exc_info.value)


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
            "  osm_source: maryland",
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
            f"  render_basemap: {tmp_path / 'maryland-latest.osm.pbf'}",
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
            f"  render_basemap: {tmp_path / 'maryland-latest.osm.pbf'}",
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


def test_extract_basemap_prefers_osm_source_cache_over_existing_extract(
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
            "  osm_source: maryland",
            f"  render_basemap: {existing_extract}",
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


def test_extract_basemap_uses_local_osm_source_override(monkeypatch, tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    maryland_path = pbf_cache_path("maryland", cache_root=cache_root)
    dc_path = pbf_cache_path("district-of-columbia", cache_root=cache_root)
    maryland_path.parent.mkdir(parents=True)
    maryland_path.write_bytes(b"maryland pbf")
    dc_path.write_bytes(b"dc pbf")
    _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            "  osm_source: maryland",
        ],
    )
    (tmp_path / DEFAULT_LOCAL_CONFIG).write_text(
        "\n".join(
            [
                "base_map:",
                "  enabled: true",
                "  osm_source: district-of-columbia",
                f"  render_basemap: {dc_path}",
                "",
            ]
        ),
        encoding="utf8",
    )
    expected_output = project_extract_path("test_project", cache_root=cache_root)
    _write_association(tmp_path, "alpha", -77.0, 39.0, size=0.004)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("civic_map_builder.basemap.shutil.which", lambda _name: "osmium")
    calls = []

    def fake_runner(command, check):
        expected_output.write_bytes(b"extract")
        calls.append((command, check))

    extracted = extract_basemap(cache_root=cache_root, command_runner=fake_runner)

    assert extracted.input_path == dc_path
    assert calls[0][0][4] == str(dc_path)


def test_extraction_source_rejects_extract_without_osm_source(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    existing_extract = project_extract_path("test_project", cache_root=cache_root)
    existing_extract.parent.mkdir(parents=True)
    existing_extract.write_bytes(b"extract")
    config_path = _write_project_config(
        tmp_path,
        extra_lines=[
            "base_map:",
            f"  render_basemap: {existing_extract}",
        ],
    )
    config = ProjectConfig.load(config_path)

    with pytest.raises(CivicMapBuilderError) as exc_info:
        extraction_source_path(config, cache_root=cache_root)

    assert "generated project extract" in str(exc_info.value)


def test_update_base_map_config_sets_osm_source_and_render_basemap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    render_basemap = tmp_path / "cache/osm/geofabrik/maryland-latest.osm.pbf"

    update_base_map_config(
        config_path=config_path,
        enabled=True,
        osm_source="maryland",
        render_basemap=render_basemap,
    )
    config = ProjectConfig.load(config_path)

    assert config.base_map.enabled is True
    assert config.base_map.osm_source == "maryland"
    assert config.base_map.render_basemap == render_basemap


def test_update_base_map_config_defaults_to_local_override(monkeypatch, tmp_path: Path) -> None:
    _write_project_config(tmp_path)
    monkeypatch.chdir(tmp_path)
    render_basemap = tmp_path / "cache/osm/geofabrik/maryland-latest.osm.pbf"

    update_base_map_config(
        enabled=True,
        osm_source="maryland",
        render_basemap=render_basemap,
    )

    project_config = ProjectConfig.load(tmp_path / "config/project.yml")
    merged_config = ProjectConfig.load()
    local_text = (tmp_path / DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
    assert project_config.base_map.enabled is False
    assert project_config.base_map.render_basemap is None
    assert merged_config.base_map.enabled is True
    assert merged_config.base_map.osm_source == "maryland"
    assert merged_config.base_map.render_basemap == render_basemap
    assert "render_basemap: " + str(render_basemap) in local_text
    assert "osm_source: maryland" in local_text


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
    _write_osm_sources_config(
        root,
        [
            "osm_sources:",
            "  district-of-columbia:",
            "    label: District of Columbia",
            "    source_url: https://example.test/district-of-columbia.osm.pbf",
            "    filename: district-of-columbia-latest.osm.pbf",
            "  maryland:",
            "    label: Maryland",
            "    source_url: https://example.test/maryland.osm.pbf",
            "    filename: maryland-latest.osm.pbf",
        ],
    )
    return config_path


def _write_osm_sources_config(root: Path, lines: list[str]) -> Path:
    config_path = root / "config/osm_sources.yml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join([*lines, ""]), encoding="utf8")
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
