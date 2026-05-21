from __future__ import annotations

import click
import typer

from . import __version__
from . import render
from .associations import check_associations, create_association
from .basemap import (
    available_downloads,
    download_label,
    pbf_cache_path,
    prepare_basemap,
    update_base_map_config,
)
from .util import load_project_config
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
) -> None:
    """Render a focused boundary-only PNG preview."""
    try:
        output_path = render.render_preview(association_id)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output_path}")


@app.command("render")
def render_all() -> None:
    """Render the full regional PNG map."""
    try:
        output_paths = render.render_regional_map()
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    for output_path in output_paths:
        typer.echo(f"Wrote {output_path}")


@basemap_app.command("download")
def basemap_download(
    download: str | None = typer.Argument(
        None,
        help="Download option, e.g. maryland. Prompts if omitted.",
    ),
    refresh: bool = typer.Option(False, "--refresh", help="Download a fresh copy."),
) -> None:
    """Download an OSM PBF into the user cache."""
    try:
        download = download or _prompt_download()
        cache_path = pbf_cache_path(download)
        typer.echo(f"Download: {download} ({download_label(download)})")
        typer.echo(f"Cache: {cache_path}")
        if cache_path.exists() and not refresh:
            typer.echo("Using existing cached file. Pass --refresh to download again.")
        else:
            typer.echo("Starting download. This may take a minute for large OSM extracts.")
        prepared = prepare_basemap(download=download, refresh=refresh, progress=_download_progress)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    if prepared.downloaded:
        typer.echo("")
    size_mb = prepared.path.stat().st_size / (1024 * 1024)
    typer.echo(f"Size: {size_mb:.1f} MB")
    if typer.confirm("Use this base map for rendering?", default=True):
        _use_cached_basemap(prepared.download)
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


def _prompt_download() -> str:
    downloads = available_downloads()
    for download in downloads:
        typer.echo(f"- {download}: {download_label(download)}")
    return typer.prompt(
        "Select OSM download",
        type=click.Choice(downloads, case_sensitive=False),
        show_choices=True,
    )


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
    typer.echo(f"enabled: {config.base_map.enabled}")
    typer.echo(f"download: {config.base_map.download or ''}")
    typer.echo(f"pbf_path: {config.base_map.pbf_path or ''}")
    typer.echo(f"padding_ratio: {config.base_map.padding_ratio}")
    if config.base_map.views:
        typer.echo("views:")
        for view in config.base_map.views:
            typer.echo(f"  {view.name}: {view.bbox}")
    else:
        typer.echo("views: none")


@basemap_app.command("use")
def basemap_use(
    download: str | None = typer.Argument(
        None,
        help="Download option, e.g. maryland. Prompts if omitted.",
    ),
) -> None:
    """Use an already cached base map for rendering."""
    try:
        _use_cached_basemap(download or _prompt_download())
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def _use_cached_basemap(download: str) -> None:
    cache_path = pbf_cache_path(download)
    if not cache_path.is_file():
        raise CivicMapBuilderError(
            f"Cached PBF not found: {cache_path}. Run 'civic-map-builder basemap download {download}' first."
        )
    update_base_map_config(enabled=True, download=download, pbf_path=cache_path)
    typer.echo(f"Enabled base maps using {cache_path}.")


@basemap_app.command("on")
def basemap_on() -> None:
    """Enable base-map rendering with the configured PBF path."""
    try:
        config = load_project_config()
        if config.base_map.pbf_path is None:
            raise CivicMapBuilderError(
                "base_map.pbf_path is not configured. Use 'civic-map-builder basemap use' first."
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
) -> None:
    """Stage PNG map assets for manual upload to a GitHub Release."""
    try:
        output_dir = render.stage_release_assets(release_name)
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output_dir}")
