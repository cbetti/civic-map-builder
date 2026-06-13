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


def test_check_suppresses_overlap_when_both_associations_declare_it(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    alpha = tmp_path / "associations/alpha"
    beta = tmp_path / "associations/beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    _write_markdown(alpha, known_overlaps=["beta"])
    _write_geojson(alpha)
    _write_markdown(beta, known_overlaps=["alpha"])
    _write_geojson(beta, lon=-77.005)

    result = check_associations(config_path=config_path)

    assert result.ok
    assert not any("overlaps" in warning for warning in result.warnings)


def test_check_errors_on_one_sided_known_overlap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    alpha = tmp_path / "associations/alpha"
    beta = tmp_path / "associations/beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    _write_markdown(alpha, known_overlaps=["beta"])
    _write_geojson(alpha)
    _write_markdown(beta)
    _write_geojson(beta, lon=-77.005)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("beta does not list alpha" in error for error in result.errors)


def test_check_errors_on_unknown_known_overlap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory, known_overlaps=["missing"])
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("references unknown association 'missing'" in error for error in result.errors)


def test_check_errors_on_self_known_overlap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory, known_overlaps=["alpha"])
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("known_overlaps cannot include itself" in error for error in result.errors)


def test_check_errors_on_malformed_known_overlap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    directory = tmp_path / "associations/alpha"
    directory.mkdir(parents=True)
    _write_markdown(directory, known_overlaps="beta")
    _write_geojson(directory)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("known_overlaps must be a list" in error for error in result.errors)


def test_check_errors_on_stale_known_overlap(tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path)
    alpha = tmp_path / "associations/alpha"
    beta = tmp_path / "associations/beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    _write_markdown(alpha, known_overlaps=["beta"])
    _write_geojson(alpha)
    _write_markdown(beta, known_overlaps=["alpha"])
    _write_geojson(beta, lon=-78.0)

    result = check_associations(config_path=config_path)

    assert not result.ok
    assert any("boundaries do not overlap" in error for error in result.errors)


def test_check_target_uses_sibling_associations_for_known_overlap_context(
    tmp_path: Path,
) -> None:
    config_path = _write_project_config(tmp_path)
    alpha = tmp_path / "associations/alpha"
    beta = tmp_path / "associations/beta"
    alpha.mkdir(parents=True)
    beta.mkdir(parents=True)
    _write_markdown(alpha, known_overlaps=["beta"])
    _write_geojson(alpha)
    _write_markdown(beta, known_overlaps=["alpha"])
    _write_geojson(beta, lon=-77.005)

    result = check_associations("alpha", config_path=config_path)

    assert result.ok
    assert not result.warnings


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


def _write_markdown(
    directory: Path,
    *,
    boundary_confidence: str | None = "provisional",
    known_overlaps: list[str] | str | None = None,
) -> None:
    metadata = [
        "---",
        f"name: {directory.name.title()}",
    ]
    if boundary_confidence is not None:
        metadata.append(f"boundary_confidence: {boundary_confidence}")
    if isinstance(known_overlaps, list):
        metadata.append("known_overlaps:")
        metadata.extend(f"  - {association_id}" for association_id in known_overlaps)
    elif known_overlaps is not None:
        metadata.append(f"known_overlaps: {known_overlaps}")
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
