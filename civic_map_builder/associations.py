from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .util import CivicMapBuilderError, ProjectConfig, load_project_config

ASSOCIATION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
BOUNDARY_MD = "boundary.md"
BOUNDARY_GEOJSON = "boundary.geojson"
SAMPLE_ASSOCIATION_PREFIX = "sample__"
BOUNDARY_CONFIDENCE_VALUES = frozenset({"draft", "provisional", "confirmed"})


@dataclass(frozen=True)
class Association:
    association_id: str
    name: str
    directory: Path
    markdown_path: Path
    geojson_path: Path
    metadata: Mapping[str, Any]
    body: str
    geometry: BaseGeometry


@dataclass
class CheckResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "CheckResult") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def create_association(association_id: str, *, config_path: Path | None = None) -> Path:
    config = load_project_config(path=config_path)
    _validate_association_id(association_id)

    directory = config.associations_dir / association_id
    if directory.exists():
        raise CivicMapBuilderError(f"Association already exists: {association_id}")

    directory.mkdir(parents=True)
    (directory / BOUNDARY_MD).write_text(_starter_markdown(association_id), encoding="utf8")
    (directory / BOUNDARY_GEOJSON).write_text(
        _starter_geojson(association_id),
        encoding="utf8",
    )
    return directory


def list_association_dirs(config: ProjectConfig) -> list[Path]:
    if not config.associations_dir.exists():
        return []
    return sorted(path for path in config.associations_dir.iterdir() if path.is_dir())


def load_association(
    association_id: str,
    *,
    config_path: Path | None = None,
) -> Association:
    config = load_project_config(path=config_path)
    return _load_association_dir(config.associations_dir / association_id)


def load_associations(
    *,
    config_path: Path | None = None,
    include_samples: bool = True,
) -> list[Association]:
    config = load_project_config(path=config_path)
    associations: list[Association] = []
    errors: list[str] = []
    for directory in list_association_dirs(config):
        if not include_samples and directory.name.startswith(SAMPLE_ASSOCIATION_PREFIX):
            continue
        try:
            associations.append(_load_association_dir(directory))
        except CivicMapBuilderError as exc:
            errors.append(str(exc))
    if errors:
        raise CivicMapBuilderError("\n".join(errors))
    return associations


def check_associations(
    association_id: str | None = None,
    *,
    config_path: Path | None = None,
) -> CheckResult:
    config = load_project_config(path=config_path)
    result = CheckResult()
    if association_id:
        directory = config.associations_dir / association_id
        if not directory.exists():
            result.errors.append(f"Association not found: {association_id}")
            return result
        directories = [directory]
    else:
        directories = list_association_dirs(config)

    loaded: list[Association] = []
    for directory in directories:
        item_result, association = _check_association_dir(directory)
        result.extend(item_result)
        if association is not None:
            loaded.append(association)

    result.warnings.extend(_overlap_warnings(loaded))
    return result


def _check_association_dir(directory: Path) -> tuple[CheckResult, Association | None]:
    result = CheckResult()
    association_id = directory.name

    if not directory.exists():
        result.errors.append(f"Association directory missing: {directory}")
        return result, None

    if not ASSOCIATION_ID_RE.match(association_id):
        result.errors.append(
            f"{association_id}: association ids must use lowercase letters, numbers, "
            "hyphens, or underscores"
        )

    markdown_path = directory / BOUNDARY_MD
    geojson_path = directory / BOUNDARY_GEOJSON
    if not markdown_path.is_file():
        result.errors.append(f"{association_id}: missing {BOUNDARY_MD}")
    if not geojson_path.is_file():
        result.errors.append(f"{association_id}: missing {BOUNDARY_GEOJSON}")
    if result.errors:
        return result, None

    try:
        association = _load_association_dir(directory)
    except CivicMapBuilderError as exc:
        result.errors.append(str(exc))
        return result, None

    if association.geometry.area < 0.000001:
        result.warnings.append(f"{association_id}: boundary area is very small")
    if association.geometry.area > 1:
        result.warnings.append(f"{association_id}: boundary area is very large")
    result.warnings.extend(_boundary_confidence_warnings(association))
    return result, association


def _load_association_dir(directory: Path) -> Association:
    association_id = directory.name
    markdown_path = directory / BOUNDARY_MD
    geojson_path = directory / BOUNDARY_GEOJSON

    metadata, body = _load_markdown(markdown_path, association_id)
    name = metadata.get("name")
    if not isinstance(name, str) or not name.strip():
        raise CivicMapBuilderError(f"{association_id}: markdown front matter requires name")

    geojson = _load_geojson(geojson_path, association_id)
    geometry = _geometry_from_geojson(geojson, association_id)

    return Association(
        association_id=association_id,
        name=name.strip(),
        directory=directory,
        markdown_path=markdown_path,
        geojson_path=geojson_path,
        metadata=metadata,
        body=body,
        geometry=geometry,
    )


def _load_markdown(path: Path, association_id: str) -> tuple[Mapping[str, Any], str]:
    try:
        text = path.read_text(encoding="utf8")
    except OSError as exc:
        raise CivicMapBuilderError(f"{association_id}: failed to read {BOUNDARY_MD}") from exc

    if not text.startswith("---\n"):
        raise CivicMapBuilderError(
            f"{association_id}: {BOUNDARY_MD} must start with YAML front matter"
        )
    try:
        _, front_matter, body = text.split("---", 2)
    except ValueError as exc:
        raise CivicMapBuilderError(
            f"{association_id}: {BOUNDARY_MD} front matter is not closed"
        ) from exc

    try:
        metadata = yaml.safe_load(front_matter) or {}
    except yaml.YAMLError as exc:
        raise CivicMapBuilderError(
            f"{association_id}: failed to parse {BOUNDARY_MD} front matter"
        ) from exc
    if not isinstance(metadata, Mapping):
        raise CivicMapBuilderError(f"{association_id}: front matter must be a mapping")
    if not body.strip():
        raise CivicMapBuilderError(f"{association_id}: markdown body is empty")
    return metadata, body.strip()


def _load_geojson(path: Path, association_id: str) -> Mapping[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf8"))
    except json.JSONDecodeError as exc:
        raise CivicMapBuilderError(f"{association_id}: malformed {BOUNDARY_GEOJSON}") from exc
    except OSError as exc:
        raise CivicMapBuilderError(f"{association_id}: failed to read {BOUNDARY_GEOJSON}") from exc

    if not isinstance(data, Mapping):
        raise CivicMapBuilderError(f"{association_id}: GeoJSON must be an object")
    return data


def _geometry_from_geojson(data: Mapping[str, Any], association_id: str) -> BaseGeometry:
    if data.get("type") != "Feature":
        raise CivicMapBuilderError(f"{association_id}: GeoJSON must be a Feature")

    properties = data.get("properties")
    if properties is not None and not isinstance(properties, Mapping):
        raise CivicMapBuilderError(f"{association_id}: GeoJSON properties must be an object")

    geometry_data = data.get("geometry")
    if not isinstance(geometry_data, Mapping):
        raise CivicMapBuilderError(f"{association_id}: GeoJSON Feature requires geometry")
    if geometry_data.get("type") not in {"Polygon", "MultiPolygon"}:
        raise CivicMapBuilderError(f"{association_id}: geometry must be Polygon or MultiPolygon")

    _validate_lon_lat_coordinates(geometry_data.get("coordinates"), association_id)

    try:
        geometry = shape(geometry_data)
    except Exception as exc:
        raise CivicMapBuilderError(f"{association_id}: failed to read GeoJSON geometry") from exc
    if geometry.is_empty:
        raise CivicMapBuilderError(f"{association_id}: geometry is empty")
    if not geometry.is_valid:
        raise CivicMapBuilderError(f"{association_id}: invalid polygon geometry")
    return geometry


def _validate_lon_lat_coordinates(coordinates: Any, association_id: str) -> None:
    points = list(_iter_points(coordinates))
    if not points:
        raise CivicMapBuilderError(f"{association_id}: geometry has no coordinates")
    for lon, lat in points:
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise CivicMapBuilderError(
                f"{association_id}: coordinates must be WGS84 lon/lat values"
            )


def _iter_points(value: Any) -> Iterable[tuple[float, float]]:
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_points(item)


def _overlap_warnings(associations: list[Association]) -> list[str]:
    warnings: list[str] = []
    for index, left in enumerate(associations):
        for right in associations[index + 1 :]:
            if left.geometry.intersection(right.geometry).area > 0:
                warnings.append(
                    f"{left.association_id}: overlaps {right.association_id}; "
                    "maintainer review needed"
                )
    return warnings


def _boundary_confidence_warnings(association: Association) -> list[str]:
    value = association.metadata.get("boundary_confidence")
    if value is None:
        return [
            f"{association.association_id}: boundary_confidence is missing; "
            "expected draft, provisional, or confirmed"
        ]
    if not isinstance(value, str) or value not in BOUNDARY_CONFIDENCE_VALUES:
        return [
            f"{association.association_id}: boundary_confidence must be one of "
            "draft, provisional, or confirmed"
        ]
    return []


def _validate_association_id(association_id: str) -> None:
    if not ASSOCIATION_ID_RE.match(association_id):
        raise CivicMapBuilderError(
            "Association ids must use lowercase letters, numbers, hyphens, or underscores."
        )


def _starter_markdown(association_id: str) -> str:
    return """---
name: TODO Association Name
boundary_confidence: draft
bylaws_source_url:
last_updated: YYYY-MM-DD
association_contact:
---

Add notes from the bylaw, map, or other boundary source here.
Sample boundary wording: bounded on the east by Main St, on the south by the CSX tracks,
on the west by Pine Ave, and on the north by Grove Park.
"""


def _starter_geojson(association_id: str) -> str:
    return json.dumps(
        {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
        indent=2,
    ) + "\n"
