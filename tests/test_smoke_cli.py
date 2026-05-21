from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from civic_map_builder.cli import app

runner = CliRunner()


def test_version_runs() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "civic-map-builder" in result.stdout


def test_help_runs() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "boundary contributions" in result.stdout.lower()


def test_new_command_creates_starter_files() -> None:
    with runner.isolated_filesystem():
        _write_project_config()

        result = runner.invoke(app, ["new", "example_association"])

        assert result.exit_code == 0
        assert "Created" in result.stdout
        assert Path("associations/example_association/boundary.md").is_file()
        assert Path("associations/example_association/boundary.geojson").is_file()


def test_check_preview_and_render_smoke() -> None:
    with runner.isolated_filesystem():
        _write_project_config()
        _write_association("alpha", "Alpha Association", -77.03, 39.0)
        _write_association("beta", "Beta Association", -77.02, 39.0)

        check_result = runner.invoke(app, ["check"])
        preview_result = runner.invoke(app, ["preview", "alpha"])
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
        assert Path("outputs/release/2026-05.1/regional-boundaries-2026-05.1.png").is_file()


def _write_project_config() -> None:
    Path("civic-map-builder.project.yml").write_text(
        "\n".join(
            [
                'project_id: "test_project"',
                'associations_dir: "associations"',
                "outputs:",
                '  previews: "outputs/previews"',
                '  maps: "outputs/maps"',
                '  release: "outputs/release"',
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
