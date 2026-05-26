from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class CivicMapBuilderError(Exception):
    """Base exception for civic-map-builder."""


DEFAULT_PROJECT_CONFIG = "config/project.yml"
DEFAULT_LOCAL_CONFIG = "config/local.yml"


@dataclass(frozen=True)
class OutputDirectories:
    previews: Path
    maps: Path
    release: Path


@dataclass(frozen=True)
class BaseMapView:
    name: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class BaseMapConfig:
    enabled: bool
    pbf_path: Path | None
    download: str | None
    padding_ratio: float
    views: tuple[BaseMapView, ...]


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    description: str | None
    associations_dir: Path
    outputs: OutputDirectories
    base_map: BaseMapConfig
    project_root: Path

    @classmethod
    def load(cls, path: Path | None = None) -> "ProjectConfig":
        """Load, validate, and resolve project configuration."""
        config_path = Path(path) if path is not None else Path(DEFAULT_PROJECT_CONFIG)
        if not config_path.is_file():
            if path is None:
                raise CivicMapBuilderError(
                    f"Project config not found: {config_path}. "
                    "Run civic-map-builder from the repository root."
                )
            raise CivicMapBuilderError(f"Project config not found: {config_path}")

        raw = _load_mapping_file(config_path, label="Project config")
        if path is None:
            local_path = Path(DEFAULT_LOCAL_CONFIG)
            if local_path.is_file():
                raw = _merge_local_base_map(raw, local_path)

        return cls._from_mapping(raw, config_path=config_path)

    @classmethod
    def _from_mapping(cls, data: Mapping[str, Any], *, config_path: Path) -> "ProjectConfig":
        root = _project_root_for_config(config_path)
        project_id = _require_str(data, "project_id", config_path)
        description = data.get("description")

        outputs_config = _require_mapping(data, "outputs", config_path)
        outputs = OutputDirectories(
            previews=_resolve_path(outputs_config, "previews", root, config_path),
            maps=_resolve_path(outputs_config, "maps", root, config_path),
            release=_resolve_path(outputs_config, "release", root, config_path),
        )

        return cls(
            project_id=project_id,
            description=description,
            associations_dir=_resolve_path(data, "associations_dir", root, config_path),
            outputs=outputs,
            base_map=_base_map_config(data.get("base_map"), root, config_path),
            project_root=root,
        )


def load_project_config(path: Path | None = None) -> ProjectConfig:
    """
    Public helper that wraps ProjectConfig.load for convenience.
    """
    return ProjectConfig.load(path=path)


def _require_mapping(
    data: Mapping[str, Any],
    key: str,
    config_path: Path,
) -> Mapping[str, Any]:
    if key not in data or data[key] is None:
        raise CivicMapBuilderError(f"Missing required '{key}' in {config_path}")
    value = data[key]
    if not isinstance(value, Mapping):
        raise CivicMapBuilderError(f"'{key}' must be a mapping/object in {config_path}")
    return value


def _load_mapping_file(path: Path, *, label: str) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf8")) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - yaml error formatting
        raise CivicMapBuilderError(f"Failed to parse {label.lower()}: {path}") from exc
    if not isinstance(raw, Mapping):
        raise CivicMapBuilderError(f"{label} must be a mapping/object: {path}")
    return dict(raw)


def _merge_local_base_map(data: Mapping[str, Any], local_path: Path) -> dict[str, Any]:
    merged = dict(data)
    local = _load_mapping_file(local_path, label="Local config")
    local_base_map = local.get("base_map")
    if local_base_map is None:
        return merged
    if not isinstance(local_base_map, Mapping):
        raise CivicMapBuilderError(f"'base_map' must be a mapping/object in {local_path}")

    base_map = merged.get("base_map")
    if base_map is None:
        base_map = {}
    if not isinstance(base_map, Mapping):
        raise CivicMapBuilderError(f"'base_map' must be a mapping/object in {DEFAULT_PROJECT_CONFIG}")
    merged_base_map = dict(base_map)
    for key in ("enabled", "pbf_path"):
        if key in local_base_map:
            merged_base_map[key] = local_base_map[key]
    merged["base_map"] = merged_base_map
    return merged


def _project_root_for_config(config_path: Path) -> Path:
    parent = config_path.parent.resolve()
    if config_path.name == "project.yml" and parent.name == "config":
        return parent.parent
    return parent


def _require_str(data: Mapping[str, Any], key: str, config_path: Path) -> str:
    if key not in data or data[key] is None:
        raise CivicMapBuilderError(f"Missing required '{key}' in {config_path}")
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise CivicMapBuilderError(f"'{key}' must be a non-empty string in {config_path}")
    return value


def _resolve_path(
    data: Mapping[str, Any],
    key: str,
    root: Path,
    config_path: Path,
) -> Path:
    if key not in data or data[key] is None:
        raise CivicMapBuilderError(f"Missing required '{key}' in {config_path}")
    value = data[key]
    if not isinstance(value, str):
        raise CivicMapBuilderError(f"'{key}' must be a string path in {config_path}")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _base_map_config(value: Any, root: Path, config_path: Path) -> BaseMapConfig:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise CivicMapBuilderError(f"'base_map' must be a mapping/object in {config_path}")

    pbf_path = _optional_path(value.get("pbf_path"), root, config_path)

    download = value.get("download")
    if download is not None and (not isinstance(download, str) or not download.strip()):
        raise CivicMapBuilderError(
            f"'base_map.download' must be a non-empty string in {config_path}"
        )

    padding_ratio = value.get("padding_ratio", 0.15)
    if not isinstance(padding_ratio, (int, float)) or padding_ratio < 0:
        raise CivicMapBuilderError(f"'base_map.padding_ratio' must be a non-negative number in {config_path}")

    views_data = value.get("views", {})
    if views_data is None:
        views_data = {}
    if not isinstance(views_data, Mapping):
        raise CivicMapBuilderError(f"'base_map.views' must be a mapping/object in {config_path}")

    views = []
    for name, view_data in views_data.items():
        if not isinstance(name, str) or not name:
            raise CivicMapBuilderError(f"'base_map.views' names must be non-empty strings in {config_path}")
        views.append(BaseMapView(name=name, bbox=_bbox_from_config(view_data, config_path)))

    return BaseMapConfig(
        enabled=bool(value.get("enabled", False)),
        pbf_path=pbf_path,
        download=download,
        padding_ratio=float(padding_ratio),
        views=tuple(views),
    )


def _bbox_from_config(value: Any, config_path: Path) -> tuple[float, float, float, float]:
    if not isinstance(value, Mapping):
        raise CivicMapBuilderError(f"Each 'base_map.views' entry must be a mapping/object in {config_path}")
    bbox = value.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise CivicMapBuilderError(f"Each 'base_map.views.*.bbox' must be a 4-number list in {config_path}")
    if not all(isinstance(item, (int, float)) for item in bbox):
        raise CivicMapBuilderError(f"Each 'base_map.views.*.bbox' must contain only numbers in {config_path}")
    minx, miny, maxx, maxy = (float(item) for item in bbox)
    if minx >= maxx or miny >= maxy:
        raise CivicMapBuilderError(f"Each 'base_map.views.*.bbox' must be [min_lon, min_lat, max_lon, max_lat] in {config_path}")
    return minx, miny, maxx, maxy


def _optional_path(value: Any, root: Path, config_path: Path) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise CivicMapBuilderError(f"'base_map.pbf_path' must be a non-empty string path in {config_path}")
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()
