"""Command line entry point."""

from pfe_validators_common import create_app
from validator_template.check import check

app = create_app(
    "validator-template",
    "One-line description (PFE-XXX-NNN).",
    check,
)
