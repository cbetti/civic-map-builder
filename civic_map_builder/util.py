from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


class CivicMapBuilderError(Exception):
    """Base exception for civic-map-builder."""


DEFAULT_PROJECT_CONFIG = "civic-map-builder.project.yml"


@dataclass(frozen=True)
class OutputDirectories:
    previews: Path
    maps: Path
    release: Path


@dataclass(frozen=True)
class ProjectConfig:
    project_id: str
    description: str | None
    associations_dir: Path
    outputs: OutputDirectories
    project_root: Path

    @classmethod
    def load(cls, path: Path | None = None) -> "ProjectConfig":
        """Load, validate, and resolve project configuration."""
        config_path = Path(path) if path is not None else Path(DEFAULT_PROJECT_CONFIG)
        if not config_path.is_file():
            raise CivicMapBuilderError(f"Project config not found: {config_path}")

        try:
            raw = yaml.safe_load(config_path.read_text(encoding="utf8")) or {}
        except yaml.YAMLError as exc:  # pragma: no cover - yaml error formatting
            raise CivicMapBuilderError(f"Failed to parse project config: {config_path}") from exc

        if not isinstance(raw, Mapping):
            raise CivicMapBuilderError(
                f"Project config must be a mapping/object: {config_path}"
            )

        return cls._from_mapping(raw, config_path=config_path)

    @classmethod
    def _from_mapping(cls, data: Mapping[str, Any], *, config_path: Path) -> "ProjectConfig":
        root = config_path.parent.resolve()
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
