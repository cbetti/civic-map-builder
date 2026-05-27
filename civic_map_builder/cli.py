from __future__ import annotations

import click
import typer
from pathlib import Path

from . import __version__
from . import render
from .associations import check_associations, create_association, load_associations
from .basemap import (
    available_osm_sources,
    extract_basemap,
    extraction_bbox,
    extraction_source_path,
    format_bbox,
    osm_source_label,
    pbf_cache_path,
    prepare_basemap,
    project_extract_path,
    update_base_map_config,
)
from .util import DEFAULT_LOCAL_CONFIG, load_project_config
from .util import CivicMapBuilderError

app = typer.Typer(help="Validate and render civic association boundary contributions.")
basemap_app = typer.Typer(help="Download and manage optional OSM base maps.")


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
) -> None:
    """
    Civic association boundary contribution CLI.
    """
    ctx.obj = {"verbose": verbose}


@app.command()
def version() -> None:
    """Show version and exit."""
    typer.echo(f"civic-map-builder {__version__}")


@app.command("new")
def new_association(
    association_id: str = typer.Argument(..., help="New association identifier."),
) -> None:
    """Create starter boundary files for an association."""
    try:
        directory = create_association(association_id)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Created {directory}")
    typer.echo("Edit boundary.md and boundary.geojson as plain text; rerun or delete them anytime.")


@app.command("check")
def check(
    association_id: str | None = typer.Argument(
        None,
        help="Association identifier. If omitted, checks all associations.",
    ),
) -> None:
    """Validate boundary contribution files."""
    try:
        result = check_associations(association_id)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for warning in result.warnings:
        typer.echo(f"WARNING: {warning}")
    for error in result.errors:
        typer.echo(f"ERROR: {error}", err=True)
    if not result.ok:
        raise typer.Exit(code=1)
    typer.echo("Check passed.")


@app.command("preview")
def preview(
    association_id: str = typer.Argument(..., help="Association identifier."),
    include_frame: bool = typer.Option(
        True,
        "--frame/--no-frame",
        help="Include the preview's outer pixel frame.",
    ),
    output_scale: int = typer.Option(
        1,
        "--output-scale",
        min=1,
        max=4,
        help="Scale final preview image dimensions.",
    ),
) -> None:
    """Render a focused boundary-only PNG preview."""
    try:
        output_path = render.render_preview(
            association_id,
            include_frame=include_frame,
            output_scale=output_scale,
        )
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output_path}")


@app.command("render")
def render_all(
    include_samples: bool = typer.Option(
        True,
        "--include-samples/--exclude-samples",
        help="Include association folders whose ids start with sample__.",
    ),
) -> None:
    """Render the full regional PNG map."""
    try:
        output_paths = render.render_regional_map(include_samples=include_samples)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for output_path in output_paths:
        typer.echo(f"Wrote {output_path}")


@basemap_app.command("download")
def basemap_download(
    osm_source: str | None = typer.Argument(
        None,
        help="OSM source, e.g. maryland. Prompts if omitted.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Download a fresh copy."),
) -> None:
    """Download an OSM PBF into the user cache."""
    try:
        osm_source = osm_source or _prompt_osm_source()
        cache_path = pbf_cache_path(osm_source)
        typer.echo(f"OSM source: {osm_source} ({osm_source_label(osm_source)})")
        typer.echo(f"Cache: {cache_path}")
        if cache_path.exists() and not refresh:
            typer.echo("Using existing cached file. Pass --refresh to download again.")
        else:
            typer.echo("Starting download. This may take a minute for large OSM extracts.")
        prepared = prepare_basemap(
            osm_source=osm_source,
            refresh=refresh,
            progress=_download_progress,
        )
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if prepared.downloaded:
        typer.echo("")
    size_mb = prepared.path.stat().st_size / (1024 * 1024)
    typer.echo(f"Size: {size_mb:.1f} MB")
    if typer.confirm("Use this base map for rendering?", default=True):
        _use_cached_basemap(prepared.osm_source)
    else:
        typer.echo("Base-map config unchanged.")


def _download_progress(received_bytes: int, total_bytes: int | None) -> None:
    received_mb = received_bytes / (1024 * 1024)
    if total_bytes is None:
        typer.echo(f"\rDownloaded {received_mb:.1f} MB", nl=False)
        return
    total_mb = total_bytes / (1024 * 1024)
    percent = (received_bytes / total_bytes) * 100
    typer.echo(f"\rDownloaded {received_mb:.1f}/{total_mb:.1f} MB ({percent:.0f}%)", nl=False)


def _prompt_osm_source() -> str:
    osm_sources = available_osm_sources()
    for osm_source in osm_sources:
        typer.echo(f"- {osm_source}: {osm_source_label(osm_source)}")
    return typer.prompt(
        "Select OSM source",
        type=click.Choice(osm_sources, case_sensitive=False),
        show_choices=True,
    )


def _prompt_basemap_source() -> str:
    config = load_project_config()
    choices = []
    extract_path = project_extract_path(config.project_id)
    if extract_path.is_file():
        typer.echo(f"- extract: Project extract ({extract_path})")
        choices.append("extract")
    for osm_source in available_osm_sources():
        typer.echo(f"- {osm_source}: {osm_source_label(osm_source)}")
        choices.append(osm_source)
    return typer.prompt(
        "Select base map",
        type=click.Choice(choices, case_sensitive=False),
        show_choices=True,
    )


@basemap_app.command("extract")
def basemap_extract() -> None:
    """Create a project-specific OSM PBF extract for faster rendering."""
    try:
        config = load_project_config()
        input_path = extraction_source_path(config)
        bounds = extraction_bbox(load_associations(), config.base_map.padding_ratio)
        output_path = project_extract_path(config.project_id)
        typer.echo(f"BBox: {format_bbox(bounds)}")
        typer.echo(f"Input: {input_path}")
        typer.echo(f"Output: {output_path}")
        extracted = extract_basemap()
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Wrote {extracted.output_path}")
    if typer.confirm("Use this extracted base map for rendering?", default=True):
        update_base_map_config(enabled=True, render_basemap=extracted.output_path)
        typer.echo(f"Enabled base maps using {extracted.output_path}.")
    else:
        typer.echo("Base-map config unchanged.")


@basemap_app.command("status")
def basemap_status() -> None:
    """Show current base-map config."""
    try:
        _show_basemap_status()
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _show_basemap_status() -> None:
    config = load_project_config()
    local_path = Path(DEFAULT_LOCAL_CONFIG)
    typer.echo(f"enabled: {config.base_map.enabled}")
    typer.echo(f"osm_source: {config.base_map.osm_source or ''}")
    typer.echo(f"render_basemap: {config.base_map.render_basemap or ''}")
    typer.echo(f"padding_ratio: {config.base_map.padding_ratio}")
    typer.echo(f"local_config: {local_path if local_path.is_file() else ''}")
    if config.base_map.views:
        typer.echo("views:")
        for view in config.base_map.views:
            typer.echo(f"  {view.name}: {view.bbox}")
    else:
        typer.echo("views: none")


@basemap_app.command("use")
def basemap_use(
    source: str | None = typer.Argument(
        None,
        help="Base-map source, e.g. extract or maryland. Prompts if omitted.",
    ),
) -> None:
    """Use an already cached base map for rendering."""
    try:
        _use_basemap_source(source or _prompt_basemap_source())
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _use_basemap_source(source: str) -> None:
    source = source.lower()
    if source == "extract":
        _use_project_extract()
    else:
        _use_cached_basemap(source)


def _use_project_extract() -> None:
    config = load_project_config()
    extract_path = project_extract_path(config.project_id)
    if not extract_path.is_file():
        raise CivicMapBuilderError(
            f"Project extract not found: {extract_path}. "
            "Run 'civic-map-builder basemap extract' first."
        )
    update_base_map_config(enabled=True, render_basemap=extract_path)
    typer.echo(f"Enabled base maps using {extract_path}.")


def _use_cached_basemap(osm_source: str) -> None:
    cache_path = pbf_cache_path(osm_source)
    if not cache_path.is_file():
        raise CivicMapBuilderError(
            f"Cached PBF not found: {cache_path}. "
            f"Run 'civic-map-builder basemap download {osm_source}' first."
        )
    update_base_map_config(
        enabled=True,
        osm_source=osm_source,
        render_basemap=cache_path,
    )
    typer.echo(f"Enabled base maps using {cache_path}.")


@basemap_app.command("on")
def basemap_on() -> None:
    """Enable base-map rendering with the configured render_basemap."""
    try:
        config = load_project_config()
        if config.base_map.render_basemap is None:
            raise CivicMapBuilderError(
                "base_map.render_basemap is not configured. "
                "Use 'civic-map-builder basemap use' first."
            )
        update_base_map_config(enabled=True)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Enabled base-map rendering.")


@basemap_app.command("off")
def basemap_off() -> None:
    """Disable base-map rendering."""
    try:
        update_base_map_config(enabled=False)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("Disabled base-map rendering.")


app.add_typer(basemap_app, name="basemap")


@app.command("release-assets")
def release_assets(
    release_name: str | None = typer.Option(
        None,
        "--release-name",
        help="Date-based release name, for example 2026-05.1.",
    ),
    include_samples: bool = typer.Option(
        False,
        "--include-samples/--exclude-samples",
        help="Include association folders whose ids start with sample__.",
    ),
) -> None:
    """Stage PNG map assets for manual upload to a GitHub Release."""
    try:
        output_dir = render.stage_release_assets(release_name, include_samples=include_samples)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output_dir}")
