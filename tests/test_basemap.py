from __future__ import annotations

from pathlib import Path

from civic_map_builder.basemap import (
    available_downloads,
    prepare_basemap,
    pbf_cache_path,
    update_base_map_config,
)
from civic_map_builder.util import ProjectConfig


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
