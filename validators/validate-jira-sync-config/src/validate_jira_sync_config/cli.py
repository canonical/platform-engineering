# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Command line interface for the gh-jira-sync-bot configuration validator."""

from pathlib import Path
from typing import Annotated

import typer
import yaml

from validate_jira_sync_config.config import validate_issue_templates, validate_settings


def main(
    config_path: Annotated[Path, typer.Argument(help="Path to .github/.jira_sync_config.yaml")],
) -> None:
    """Validate the mandatory fields of a gh-jira-sync-bot configuration."""
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        typer.echo(f"ERROR: cannot read {config_path}: {error}", err=True)
        raise typer.Exit(code=1) from error
    errors = validate_settings(config)
    issue_template_dir = config_path.resolve().parent / "ISSUE_TEMPLATE"
    if issue_template_dir.is_dir():
        errors += validate_issue_templates(issue_template_dir)
    for error in errors:
        typer.echo(f"ERROR: {error}", err=True)
    if errors:
        raise typer.Exit(code=1)
    typer.echo(f"{config_path}: OK")


app = typer.Typer(add_completion=False)
app.command(no_args_is_help=True)(main)

if __name__ == "__main__":
    app()
