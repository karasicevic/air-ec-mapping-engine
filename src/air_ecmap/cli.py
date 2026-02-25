"""CLI placeholder for AIR EC+Mapping engine."""

from __future__ import annotations

import typer

app = typer.Typer(help="AIR EC+Mapping CLI (placeholder).")


@app.command()
def version() -> None:
    """Show placeholder version output."""
    typer.echo("air-ecmap bootstrap 0.1.0")


def main() -> None:
    """Entrypoint for console scripts."""
    app()


if __name__ == "__main__":
    main()