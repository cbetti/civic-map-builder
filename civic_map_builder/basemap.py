from __future__ import annotations

import shutil
import subprocess
from importlib.util import find_spec
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from shapely.geometry import LineString, Polygon, box
from shapely.geometry.base import BaseGeometry

from .associations import Association, load_associations
from .util import BaseMapConfig, CivicMapBuilderError, ProjectConfig, load_project_config
import yaml

APP_NAME = "civic-map-builder"
DOWNLOAD_OPTIONS = {
    "district-of-columbia": {
        "label": "District of Columbia",
        "source_url": (
            "https://download.geofabrik.de/north-america/us/"
            "district-of-columbia-latest.osm.pbf"
        ),
        "filename": "district-of-columbia-latest.osm.pbf",
    },
    "maryland": {
        "label": "Maryland",
        "source_url": "https://download.geofabrik.de/north-america/us/maryland-latest.osm.pbf",
        "filename": "maryland-latest.osm.pbf",
    },
}

ROAD_TAGS = {
    "motorway",
    "trunk",
    "primary",
    "secondary",
    "tertiary",
    "residential",
    "unclassified",
    "service",
}
RAIL_TAGS = {"rail", "light_rail", "subway", "tram"}
PARK_LANDUSE_TAGS = {"grass", "recreation_ground", "village_green"}
PARK_NATURAL_TAGS = {"wood", "scrub", "heath"}
WATER_TAGS = {"water", "bay", "strait"}


@dataclass
class BaseMapFeatures:
    roads: list[tuple[LineString, str]] = field(default_factory=list)
    rail: list[LineString] = field(default_factory=list)
    water: list[BaseGeometry] = field(default_factory=list)
    parks: list[BaseGeometry] = field(default_factory=list)


@dataclass(frozen=True)
class PreparedBaseMap:
    download: str
    source_url: str
    path: Path
    downloaded: bool


@dataclass(frozen=True)
class ExtractedBaseMap:
    input_path: Path
    output_path: Path
    bbox: tuple[float, float, float, float]
    command: tuple[str, ...]


def default_cache_root() -> Path:
    try:
        from platformdirs import user_cache_path
    except ImportError as exc:
        raise CivicMapBuilderError(
            "Base-map cache support requires optional dependencies. "
            'Install with: pip install -e ".[dev,basemap]"'
        ) from exc
    return user_cache_path(APP_NAME, appauthor=False)


def available_downloads() -> tuple[str, ...]:
    return tuple(sorted(DOWNLOAD_OPTIONS))


def download_label(download: str) -> str:
    return _download_option(download)["label"]


def pbf_cache_path(download: str, cache_root: Path | None = None) -> Path:
    option = _download_option(download)
    root = cache_root or default_cache_root()
    return root / "osm" / "geofabrik" / option["filename"]


def project_extract_path(project_id: str, cache_root: Path | None = None) -> Path:
    root = cache_root or default_cache_root()
    return root / "osm" / "extracts" / f"{project_id}-basemap.osm.pbf"


def extraction_source_path(config: ProjectConfig, cache_root: Path | None = None) -> Path:
    if config.base_map.download is not None:
        download_path = pbf_cache_path(config.base_map.download, cache_root=cache_root)
        if download_path.is_file():
            return download_path
        if config.base_map.pbf_path is not None and not _is_extract_path(
            config.base_map.pbf_path,
            cache_root=cache_root,
        ):
            return _existing_pbf_path(config.base_map.pbf_path)
        raise CivicMapBuilderError(
            f"Cached regional PBF not found: {download_path}. "
            f"Run 'civic-map-builder basemap download {config.base_map.download}' first."
        )

    if config.base_map.pbf_path is None:
        raise CivicMapBuilderError(
            "base_map.pbf_path is not configured. "
            "Run 'civic-map-builder basemap download <download>' first."
        )
    if _is_extract_path(config.base_map.pbf_path, cache_root=cache_root):
        raise CivicMapBuilderError(
            "base_map.pbf_path points to a generated project extract, not a regional source PBF. "
            "Configure base_map.download or set base_map.pbf_path to a regional .osm.pbf before extracting."
        )
    return _existing_pbf_path(config.base_map.pbf_path)


def extraction_bbox(
    associations: Sequence[Association],
    padding_ratio: float,
) -> tuple[float, float, float, float]:
    if not associations:
        raise CivicMapBuilderError("No associations found for base-map extraction.")
    return _padded_bounds(
        _combined_bounds([association.geometry for association in associations]),
        padding_ratio,
    )


def format_bbox(bounds: tuple[float, float, float, float]) -> str:
    return ",".join(f"{value:.8f}".rstrip("0").rstrip(".") for value in bounds)


def build_extract_command(
    *,
    osmium_path: str,
    bounds: tuple[float, float, float, float],
    input_path: Path,
    output_path: Path,
) -> tuple[str, ...]:
    return (
        osmium_path,
        "extract",
        "--bbox",
        format_bbox(bounds),
        str(input_path),
        "-o",
        str(output_path),
        "--overwrite",
    )


def extract_basemap(
    *,
    config_path: Path | None = None,
    cache_root: Path | None = None,
    command_runner: Callable[..., Any] | None = None,
) -> ExtractedBaseMap:
    config = load_project_config(path=config_path)
    input_path = extraction_source_path(config, cache_root=cache_root)

    osmium_path = shutil.which("osmium")
    if osmium_path is None:
        raise CivicMapBuilderError(
            "The 'osmium' CLI is required for base-map extraction.\n"
            "Install hints:\n"
            "- Linux: sudo apt install osmium-tool\n"
            "- macOS: brew install osmium-tool\n"
            "- Windows: use WSL or install osmium-tool manually."
        )

    associations = load_associations(config_path=config_path)
    bounds = extraction_bbox(associations, config.base_map.padding_ratio)
    output_path = project_extract_path(config.project_id, cache_root=cache_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = build_extract_command(
        osmium_path=osmium_path,
        bounds=bounds,
        input_path=input_path,
        output_path=output_path,
    )
    runner = command_runner or subprocess.run
    try:
        runner(list(command), check=True)
    except subprocess.CalledProcessError as exc:
        raise CivicMapBuilderError(f"osmium extract failed with exit code {exc.returncode}.") from exc
    except OSError as exc:
        raise CivicMapBuilderError(f"Failed to run osmium extract: {exc}") from exc
    if not output_path.is_file():
        raise CivicMapBuilderError(f"osmium extract did not create expected output: {output_path}")
    return ExtractedBaseMap(
        input_path=input_path,
        output_path=output_path,
        bbox=bounds,
        command=command,
    )


def prepare_basemap(
    *,
    download: str | None = None,
    config_path: Path | None = None,
    cache_root: Path | None = None,
    refresh: bool = False,
    progress: Callable[[int, int | None], None] | None = None,
) -> PreparedBaseMap:
    config = load_project_config(path=config_path)
    selected_download = download or config.base_map.download
    if selected_download is None:
        raise CivicMapBuilderError(
            "base_map.download is not configured. Available options: "
            + ", ".join(available_downloads())
        )
    option = _download_option(selected_download)
    target_path = pbf_cache_path(selected_download, cache_root=cache_root)
    if target_path.exists() and not refresh:
        return PreparedBaseMap(
            download=selected_download,
            source_url=option["source_url"],
            path=target_path,
            downloaded=False,
        )

    try:
        import requests
    except ImportError as exc:
        raise CivicMapBuilderError(
            "Downloading base-map data requires optional dependencies. "
            'Install with: pip install -e ".[dev,basemap]"'
        ) from exc

    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(target_path.suffix + ".part")
    with requests.get(option["source_url"], stream=True, timeout=30) as response:
        response.raise_for_status()
        total_bytes = _content_length(response)
        received_bytes = 0
        with temp_path.open("wb") as file_obj:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file_obj.write(chunk)
                    received_bytes += len(chunk)
                    if progress is not None:
                        progress(received_bytes, total_bytes)
    temp_path.replace(target_path)
    return PreparedBaseMap(
        download=selected_download,
        source_url=option["source_url"],
        path=target_path,
        downloaded=True,
    )


def configured_pbf_path(config: BaseMapConfig) -> Path:
    if config.pbf_path is None:
        raise CivicMapBuilderError(
            "base_map.enabled is true, but base_map.pbf_path is not configured. "
            "Run 'civic-map-builder basemap download <download>' or "
            "'civic-map-builder basemap use <download>'."
        )
    if not config.pbf_path.is_file():
        raise CivicMapBuilderError(f"Configured base_map.pbf_path does not exist: {config.pbf_path}")
    return config.pbf_path


def load_basemap_features(
    *,
    pbf_path: Path,
    bounds: tuple[float, float, float, float],
) -> BaseMapFeatures:
    if not pbf_path.is_file():
        raise CivicMapBuilderError(f"Base-map PBF not found: {pbf_path}")
    if find_spec("osmium") is None:
        raise CivicMapBuilderError(
            "Rendering OSM base maps requires optional dependencies. "
            'Install with: pip install -e ".[dev,basemap]"'
        )

    features = BaseMapFeatures()
    handler = _BaseMapHandler(features=features, bounds=bounds)
    handler.apply_file(str(pbf_path), locations=True)
    return features


class _BaseMapHandler:
    def __init__(
        self,
        *,
        features: BaseMapFeatures,
        bounds: tuple[float, float, float, float],
    ) -> None:
        import osmium

        class Handler(osmium.SimpleHandler):
            def way(inner_self, way: Any) -> None:
                _handle_way(way, features, bounds)

            def area(inner_self, area: Any) -> None:
                _handle_area(area, features, bounds)

        self._handler = Handler()

    def apply_file(self, path: str, *, locations: bool) -> None:
        self._handler.apply_file(path, locations=locations)


def _handle_way(
    way: Any,
    features: BaseMapFeatures,
    bounds: tuple[float, float, float, float],
) -> None:
    tags = _tags_dict(way.tags)
    highway = tags.get("highway")
    railway = tags.get("railway")
    if highway not in ROAD_TAGS and railway not in RAIL_TAGS:
        return

    line = _line_from_way(way)
    if line is None or not _intersects_bounds(line, bounds):
        return
    clipped = line.intersection(box(*bounds))
    if clipped.is_empty:
        return
    if highway in ROAD_TAGS:
        for part in _line_parts(clipped):
            features.roads.append((part, highway))
    if railway in RAIL_TAGS:
        features.rail.extend(_line_parts(clipped))


def _handle_area(
    area: Any,
    features: BaseMapFeatures,
    bounds: tuple[float, float, float, float],
) -> None:
    tags = _tags_dict(area.tags)
    polygon = _polygon_from_area(area)
    if polygon is None or not _intersects_bounds(polygon, bounds):
        return
    clipped = polygon.intersection(box(*bounds))
    if clipped.is_empty:
        return

    if _is_water(tags):
        features.water.append(clipped)
    if _is_park(tags):
        features.parks.append(clipped)


def _tags_dict(tags: Any) -> dict[str, str]:
    return {tag.k: tag.v for tag in tags}


def _line_from_way(way: Any) -> LineString | None:
    coords = []
    for node in way.nodes:
        try:
            coords.append((float(node.lon), float(node.lat)))
        except Exception:
            return None
    if len(coords) < 2:
        return None
    return LineString(coords)


def _polygon_from_area(area: Any) -> Polygon | None:
    try:
        rings = list(area.outer_rings())
    except Exception:
        return None
    if not rings:
        return None
    coords = []
    for node in rings[0]:
        try:
            coords.append((float(node.lon), float(node.lat)))
        except Exception:
            return None
    if len(coords) < 4:
        return None
    return Polygon(coords)


def _intersects_bounds(geometry: BaseGeometry, bounds: tuple[float, float, float, float]) -> bool:
    return geometry.intersects(box(*bounds))


def _existing_pbf_path(path: Path) -> Path:
    if not path.is_file():
        raise CivicMapBuilderError(f"Configured base_map.pbf_path does not exist: {path}")
    return path


def _is_extract_path(path: Path, cache_root: Path | None = None) -> bool:
    root = cache_root or default_cache_root()
    try:
        path.resolve().relative_to((root / "osm" / "extracts").resolve())
    except ValueError:
        return False
    return True


def _combined_bounds(geometries: Sequence[BaseGeometry]) -> tuple[float, float, float, float]:
    minx = min(geometry.bounds[0] for geometry in geometries)
    miny = min(geometry.bounds[1] for geometry in geometries)
    maxx = max(geometry.bounds[2] for geometry in geometries)
    maxy = max(geometry.bounds[3] for geometry in geometries)
    return minx, miny, maxx, maxy


def _padded_bounds(
    bounds: tuple[float, float, float, float],
    padding_ratio: float,
) -> tuple[float, float, float, float]:
    minx, miny, maxx, maxy = bounds
    width = maxx - minx
    height = maxy - miny
    padding_x = width * padding_ratio
    padding_y = height * padding_ratio
    return minx - padding_x, miny - padding_y, maxx + padding_x, maxy + padding_y


def _line_parts(geometry: BaseGeometry) -> list[LineString]:
    if isinstance(geometry, LineString):
        return [geometry]
    return [part for part in getattr(geometry, "geoms", []) if isinstance(part, LineString)]


def _is_water(tags: dict[str, str]) -> bool:
    return (
        tags.get("natural") in WATER_TAGS
        or tags.get("water") in {"pond", "lake", "reservoir", "river"}
        or tags.get("landuse") == "reservoir"
    )


def _is_park(tags: dict[str, str]) -> bool:
    return (
        tags.get("leisure") in {"park", "garden", "recreation_ground"}
        or tags.get("landuse") in PARK_LANDUSE_TAGS
        or tags.get("natural") in PARK_NATURAL_TAGS
    )


def copy_for_tests(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def update_base_map_config(
    *,
    config_path: Path | None = None,
    enabled: bool | None = None,
    download: str | None = None,
    pbf_path: Path | None = None,
) -> None:
    target_path = config_path or Path("civic-map-builder.project.yml")
    data = _load_config_mapping(target_path)
    base_map = data.get("base_map")
    if base_map is None:
        base_map = {}
        data["base_map"] = base_map
    if not isinstance(base_map, dict):
        raise CivicMapBuilderError(f"'base_map' must be a mapping/object in {target_path}")

    if enabled is not None:
        base_map["enabled"] = enabled
    if download is not None:
        _download_option(download)
        base_map["download"] = download
    if pbf_path is not None:
        base_map["pbf_path"] = str(pbf_path.expanduser().resolve())

    base_map.setdefault("padding_ratio", 0.15)
    base_map.setdefault("views", {})
    target_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf8")


def _download_option(download: str) -> dict[str, str]:
    try:
        return DOWNLOAD_OPTIONS[download]
    except KeyError as exc:
        raise CivicMapBuilderError(
            f"Unknown base_map.download option '{download}'. "
            "Available options: " + ", ".join(available_downloads())
        ) from exc


def _load_config_mapping(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise CivicMapBuilderError(f"Project config not found: {config_path}")
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf8")) or {}
    except yaml.YAMLError as exc:
        raise CivicMapBuilderError(f"Failed to parse project config: {config_path}") from exc
    if not isinstance(data, Mapping):
        raise CivicMapBuilderError(f"Project config must be a mapping/object: {config_path}")
    return dict(data)


def _content_length(response: Any) -> int | None:
    value = response.headers.get("content-length")
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
