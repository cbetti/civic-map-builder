from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

from typer.testing import CliRunner

from civic_map_builder.cli import app
from civic_map_builder.util import DEFAULT_LOCAL_CONFIG, ProjectConfig

runner = CliRunner()


@contextmanager
def isolated_filesystem() -> Iterator[Path]:
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as directory:
        os.chdir(directory)
        try:
            yield Path(directory)
        finally:
            os.chdir(original_cwd)


def test_version_runs() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "civic-map-builder" in result.stdout


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "boundary contributions" in result.stdout.lower()


def test_config_backed_command_requires_repository_root() -> None:
    with isolated_filesystem():
        result = runner.invoke(app, ["check"])

        assert result.exit_code == 1
        assert "Run civic-map-builder from the repository root." in result.stderr


def test_new_command_creates_starter_files() -> None:
    with isolated_filesystem():
        _write_project_config()

        result = runner.invoke(app, ["new", "example_association"])

        assert result.exit_code == 0
        assert "Created" in result.stdout
        assert Path("associations/example_association/boundary.md").is_file()
        assert Path("associations/example_association/boundary.geojson").is_file()
        assert (
            "boundary_confidence: draft"
            in Path("associations/example_association/boundary.md").read_text(encoding="utf8")
        )
        assert (
            "association_contact:"
            in Path("associations/example_association/boundary.md").read_text(encoding="utf8")
        )


def test_check_preview_and_render_smoke() -> None:
    with isolated_filesystem():
        _write_project_config()
        _write_association("alpha", "Alpha Association", -77.03, 39.0)
        _write_association("beta", "Beta Association", -77.02, 39.0)

        check_result = runner.invoke(app, ["check"])
        preview_result = runner.invoke(
            app,
            ["preview", "alpha", "--no-frame", "--output-scale", "2"],
        )
        render_result = runner.invoke(app, ["render"])
        release_result = runner.invoke(
            app,
            ["release-assets", "--release-name", "2026-05.1"],
        )

        assert check_result.exit_code == 0
        assert preview_result.exit_code == 0
        assert render_result.exit_code == 0
        assert release_result.exit_code == 0
        assert Path("outputs/previews/alpha.png").is_file()
        assert Path("outputs/maps/regional-boundaries.png").is_file()
        assert Path("outputs/release/2026-05.1/test-project-2026-05.1.png").is_file()
        assert Path("outputs/release/2026-05.1/test-project-2026-05.1.zip").is_file()


def test_basemap_status_and_off_smoke() -> None:
    with isolated_filesystem():
        _write_project_config()

        help_result = runner.invoke(app, ["basemap", "--help"])
        status_result = runner.invoke(app, ["basemap", "status"])
        off_result = runner.invoke(app, ["basemap", "off"])

        assert help_result.exit_code == 0
        assert status_result.exit_code == 0
        assert "enabled:" in status_result.stdout
        assert "local_config:" in status_result.stdout
        assert off_result.exit_code == 0


def test_basemap_extract_help_runs() -> None:
    result = runner.invoke(app, ["basemap", "extract", "--help"])

    assert result.exit_code == 0
    assert "faster rendering" in result.stdout


def test_basemap_download_cached_yes_updates_config(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        _write_project_config()
        cache_path = tmp_path / "maryland-latest.osm.pbf"
        cache_path.write_bytes(b"cached")
        monkeypatch.setattr("civic_map_builder.cli.pbf_cache_path", lambda _download: cache_path)
        monkeypatch.setattr(
            "civic_map_builder.basemap.pbf_cache_path",
            lambda _source, cache_root=None: cache_path,
        )

        result = runner.invoke(app, ["basemap", "download", "maryland"], input="y\n")

        assert result.exit_code == 0
        assert "Using existing cached file" in result.stdout
        assert "Enabled base maps" in result.stdout
        config_text = Path(DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
        assert "osm_source: maryland" in config_text
        assert "render_basemap: " + str(cache_path) in config_text
        assert "render_basemap: " not in Path("config/project.yml").read_text(
            encoding="utf8"
        )


def test_basemap_download_cached_no_leaves_config(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        _write_project_config()
        cache_path = tmp_path / "maryland-latest.osm.pbf"
        cache_path.write_bytes(b"cached")
        monkeypatch.setattr("civic_map_builder.cli.pbf_cache_path", lambda _download: cache_path)
        monkeypatch.setattr(
            "civic_map_builder.basemap.pbf_cache_path",
            lambda _source, cache_root=None: cache_path,
        )

        result = runner.invoke(app, ["basemap", "download", "maryland"], input="n\n")

        assert result.exit_code == 0
        assert "Base-map config unchanged." in result.stdout
        assert not Path(DEFAULT_LOCAL_CONFIG).exists()


def test_basemap_use_switches_to_cached_download(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        _write_project_config()
        cache_path = tmp_path / "district-of-columbia-latest.osm.pbf"
        cache_path.write_bytes(b"cached")
        monkeypatch.setattr("civic_map_builder.cli.pbf_cache_path", lambda _download: cache_path)

        result = runner.invoke(app, ["basemap", "use", "district-of-columbia"])

        assert result.exit_code == 0
        config_text = Path(DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
        assert "osm_source: district-of-columbia" in config_text
        assert "render_basemap: " + str(cache_path) in config_text
        assert "enabled: true" in config_text
        assert "osm_source: district-of-columbia" not in Path(
            "config/project.yml"
        ).read_text(encoding="utf8")


def test_basemap_use_extract_switches_to_project_extract(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        extract_path = tmp_path / "test_project-basemap.osm.pbf"
        extract_path.write_bytes(b"extract")
        _write_project_config(
            extra_lines=[
                "base_map:",
                "  osm_source: maryland",
            ]
        )
        monkeypatch.setattr(
            "civic_map_builder.cli.project_extract_path",
            lambda _project_id: extract_path,
        )

        result = runner.invoke(app, ["basemap", "use", "extract"])

        assert result.exit_code == 0
        config_text = Path(DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
        assert "render_basemap: " + str(extract_path) in config_text
        assert "enabled: true" in config_text
        assert ProjectConfig.load().base_map.osm_source == "maryland"


def test_basemap_use_prompt_offers_project_extract(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        extract_path = tmp_path / "test_project-basemap.osm.pbf"
        extract_path.write_bytes(b"extract")
        _write_project_config()
        monkeypatch.setattr(
            "civic_map_builder.cli.project_extract_path",
            lambda _project_id: extract_path,
        )

        result = runner.invoke(app, ["basemap", "use"], input="extract\n")

        assert result.exit_code == 0
        assert "- extract: Project extract" in result.stdout
        assert "- district-of-columbia: District of Columbia" in result.stdout
        assert "- maryland: Maryland" in result.stdout
        config_text = Path(DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
        assert "render_basemap: " + str(extract_path) in config_text


def test_basemap_use_extract_fails_when_project_extract_missing(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        missing_path = tmp_path / "missing-basemap.osm.pbf"
        _write_project_config()
        monkeypatch.setattr(
            "civic_map_builder.cli.project_extract_path",
            lambda _project_id: missing_path,
        )

        result = runner.invoke(app, ["basemap", "use", "extract"])

        assert result.exit_code == 1
        assert "Project extract not found" in result.stderr


def test_basemap_use_fails_when_cached_file_missing(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        _write_project_config()
        missing_path = tmp_path / "missing.osm.pbf"
        monkeypatch.setattr("civic_map_builder.cli.pbf_cache_path", lambda _download: missing_path)

        result = runner.invoke(app, ["basemap", "use", "maryland"])

        assert result.exit_code == 1
        assert "Cached PBF not found" in result.stderr


def test_basemap_extract_yes_updates_config(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        input_path = tmp_path / "maryland-latest.osm.pbf"
        input_path.write_bytes(b"pbf")
        extract_path = tmp_path / "test_project-basemap.osm.pbf"
        extract_path.write_bytes(b"extract")
        _write_project_config(
            extra_lines=[
                "base_map:",
                f"  render_basemap: {input_path}",
            ]
        )
        _write_association("alpha", "Alpha Association", -77.03, 39.0)
        monkeypatch.setattr(
            "civic_map_builder.cli.project_extract_path",
            lambda _project_id: extract_path,
        )
        monkeypatch.setattr(
            "civic_map_builder.cli.extract_basemap",
            lambda: SimpleNamespace(output_path=extract_path),
        )

        result = runner.invoke(app, ["basemap", "extract"], input="y\n")

        assert result.exit_code == 0
        assert "BBox:" in result.stdout
        assert "Input: " + str(input_path) in result.stdout
        assert "Output: " + str(extract_path) in result.stdout
        config_text = Path(DEFAULT_LOCAL_CONFIG).read_text(encoding="utf8")
        assert "enabled: true" in config_text
        assert "render_basemap: " + str(extract_path) in config_text
        assert "osm_source:" not in config_text
        assert "render_basemap: " + str(extract_path) not in Path(
            "config/project.yml"
        ).read_text(encoding="utf8")


def test_basemap_extract_no_preserves_config(monkeypatch, tmp_path: Path) -> None:
    with isolated_filesystem():
        input_path = tmp_path / "maryland-latest.osm.pbf"
        input_path.write_bytes(b"pbf")
        extract_path = tmp_path / "test_project-basemap.osm.pbf"
        _write_project_config(
            extra_lines=[
                "base_map:",
                f"  render_basemap: {input_path}",
            ]
        )
        _write_association("alpha", "Alpha Association", -77.03, 39.0)
        monkeypatch.setattr(
            "civic_map_builder.cli.project_extract_path",
            lambda _project_id: extract_path,
        )
        monkeypatch.setattr(
            "civic_map_builder.cli.extract_basemap",
            lambda: SimpleNamespace(output_path=extract_path),
        )

        result = runner.invoke(app, ["basemap", "extract"], input="n\n")

        assert result.exit_code == 0
        assert "Base-map config unchanged." in result.stdout
        config_text = Path("config/project.yml").read_text(encoding="utf8")
        assert "render_basemap: " + str(input_path) in config_text
        assert "render_basemap: " + str(extract_path) not in config_text
        assert not Path(DEFAULT_LOCAL_CONFIG).exists()


def _write_project_config(*, extra_lines: list[str] | None = None) -> None:
    extra_lines = extra_lines or []
    Path("config").mkdir(parents=True, exist_ok=True)
    Path("config/project.yml").write_text(
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
    Path("config/osm_sources.yml").write_text(
        "\n".join(
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
                "",
            ]
        ),
        encoding="utf8",
    )


def _write_association(
    association_id: str,
    name: str,
    lon: float,
    lat: float,
    *,
    size: float = 0.004,
) -> None:
    directory = Path("associations") / association_id
    directory.mkdir(parents=True)
    (directory / "boundary.md").write_text(
        "\n".join(
            [
                "---",
                f"name: {name}",
                "boundary_confidence: provisional",
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
