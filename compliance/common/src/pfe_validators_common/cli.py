"""Standard command line for validators, built with Typer."""

import enum
import os
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Annotated

import typer

from pfe_validators_common.findings import Finding
from pfe_validators_common.output import render

Check = Callable[[Sequence[Path]], Sequence[Finding]]

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2


class OutputFormat(str, enum.Enum):
    """Supported output formats."""

    TEXT = "text"
    GITHUB = "github"
    JSON = "json"


def _default_format() -> OutputFormat:
    return OutputFormat.GITHUB if os.environ.get("GITHUB_ACTIONS") == "true" else OutputFormat.TEXT


def create_app(name: str, description: str, check: Check) -> typer.Typer:
    """Create the command line application of a validator.

    The application takes ``PATH...`` arguments and a ``--format`` option, and exits with
    ``0`` when there are no findings, ``1`` when findings were reported and ``2`` on usage
    or runtime errors.

    Args:
        name: Program name.
        description: Short description shown in ``--help``.
        check: Callable receiving the paths to scan and returning findings.

    Returns:
        A Typer application, to be used as the console script entry point.
    """
    app = typer.Typer(
        name=name,
        help=description,
        add_completion=False,
        pretty_exceptions_enable=False,
    )

    @app.command(name=name, help=description)
    def run(
        paths: Annotated[
            list[Path] | None,
            typer.Argument(help="Files or directories to check (default: current directory)."),
        ] = None,
        output_format: Annotated[
            OutputFormat | None,
            typer.Option(
                "--format",
                help="Output format (default: github on GitHub Actions, text otherwise).",
            ),
        ] = None,
    ) -> None:
        targets = paths or [Path(".")]
        fmt = output_format or _default_format()

        missing = [p for p in targets if not p.exists()]
        if missing:
            typer.echo(f"{name}: path not found: {', '.join(map(str, missing))}", err=True)
            raise typer.Exit(EXIT_ERROR)

        try:
            findings = list(check(targets))
        except Exception as exc:
            typer.echo(f"{name}: error: {exc}", err=True)
            raise typer.Exit(EXIT_ERROR) from exc

        output = render(findings, fmt.value)
        if output:
            typer.echo(output)
        if fmt is not OutputFormat.JSON:
            typer.echo(f"{name}: {len(findings)} finding(s)", err=True)
        raise typer.Exit(EXIT_FINDINGS if findings else EXIT_OK)

    return app


__all__ = ["Check", "OutputFormat", "create_app"]
