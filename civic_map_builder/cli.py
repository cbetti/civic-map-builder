from __future__ import annotations

import typer

from . import __version__
from . import render
from .associations import check_associations, create_association
from .util import CivicMapBuilderError

app = typer.Typer(help="Validate and render civic association boundary contributions.")


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
    """Render the full boundary-only regional PNG map."""
    try:
        output_path = render.render_regional_map()
    except CivicMapBuilderError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Wrote {output_path}")


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
