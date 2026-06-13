from __future__ import annotations

from pathlib import Path

from civic_map_builder.associations import check_associations


def test_check_catches_missing_paired_file(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("missing boundary.geojson" in error for error in result.errors)


def test_check_catches_invalid_folder_id(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/Alpha Association"
    directory.mkdir(parents=True)
    _write_markdown(directory)
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("association ids must use" in error for error in result.errors)


def test_check_catches_malformed_front_matter(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    (directory / "boundary.md").write_text("---\nid: [\n---\nBody\n", encoding="utf8")
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("failed to parse" in error for error in result.errors)


def test_check_catches_malformed_geojson(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory)
    (directory / "boundary.geojson").write_text("{", encoding="utf8")

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("malformed boundary.geojson" in error for error in result.errors)


def test_check_catches_invalid_polygon(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory)
    _write_geojson(
        directory,
        coordinates=[
            [
                [-77.0, 39.0],
                [-76.99, 39.01],
                [-77.0, 39.01],
                [-76.99, 39.0],
                [-77.0, 39.0],
            ]
        ],
    )

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("invalid polygon geometry" in error for error in result.errors)


def test_check_warns_on_overlap_without_failing(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    alpha = tmp_path / "associations/alpha"
    beta = tmp_path / "associations/beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    _write_markdown(alpha)
    _write_geojson(alpha)
    _write_markdown(beta)
    _write_geojson(beta, lon=-77.005)

    result = check_associations(config_path=config_path)

    assert result.ok
    assert any("overlaps" in warning for warning in result.warnings)


def test_check_accepts_boundary_confidence_values(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    for value in ("draft", "provisional", "confirmed"):
        directory = tmp_path / f"associations/{value}"
        directory.mkdir(parents=True)
        _write_markdown(directory, boundary_confidence=value)
        _write_geojson(directory, lon=-77.0 + len(value) / 100)

    result = check_associations(config_path=config_path)

    assert result.ok
    assert not any("boundary_confidence" in warning for warning in result.warnings)


def test_check_warns_on_missing_boundary_confidence(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory, boundary_confidence=None)
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert result.ok
    assert any("boundary_confidence is missing" in warning for warning in result.warnings)


def test_check_warns_on_invalid_boundary_confidence(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory, boundary_confidence="unverified")
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert result.ok
    assert any("boundary_confidence must be one of" in warning for warning in result.warnings)


def _write_project_config(root: Path) -> Path:
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
                "",
            ]
        ),
        encoding="utf8",
    )
    return config_path


def _write_markdown(directory: Path, *, boundary_confidence: str | None = "provisional") -> None:
    metadata = [
        "---",
        f"name: {directory.name.title()}",
    ]
    if boundary_confidence is not None:
        metadata.append(f"boundary_confidence: {boundary_confidence}")
    metadata.append("---")
    (directory / "boundary.md").write_text(
        "\n".join(
            [
                *metadata,
                "",
                "Boundary text.",
                "",
            ]
        ),
        encoding="utf8",
    )


def _write_geojson(
    directory: Path,
    *,
    lon: float = -77.0,
    lat: float = 39.0,
    size: float = 0.01,
    coordinates: list[list[list[float]]] | None = None,
) -> None:
    coordinates = coordinates or [
        [
            [lon, lat],
            [lon + size, lat],
            [lon + size, lat + size],
            [lon, lat + size],
            [lon, lat],
        ]
    ]
    (directory / "boundary.geojson").write_text(
        f"""{{
  "type": "Feature",
  "properties": {{}},
  "geometry": {{"type": "Polygon", "coordinates": {coordinates}}}
}}
""",
        encoding="utf8",
    )
