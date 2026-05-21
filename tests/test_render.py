from __future__ import annotations

from pathlib import Path

from civic_map_builder import render


def test_render_outputs_nontrivial_pngs(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    _write_association(tmp_path, "alpha", "Alpha Association", -77.03, 39.0)
    _write_association(tmp_path, "beta", "Beta Association", -77.02, 39.0)

    preview_path = render.render_preview("alpha", config_path=config_path)
    regional_path = render.render_regional_map(config_path=config_path)

    assert preview_path.is_file()
    assert regional_path.is_file()
    assert preview_path.stat().st_size > 1_000
    assert regional_path.stat().st_size > preview_path.stat().st_size


def _write_project_config(root: Path) -> Path:
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
