"""Command line entry point."""

from check_devenv.check import check
from pfe_validators_common import create_app

app = create_app(
    "check-devenv",
    (
        "Check the opencode development environment: snap version, LSP and default "
        "model (PFE-DEV-001). The optional path is the project directory whose opencode "
        "config is taken into account."
    ),
    check,
)
