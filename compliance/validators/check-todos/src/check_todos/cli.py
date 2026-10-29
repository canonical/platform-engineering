"""Command line entry point."""

from check_todos.check import check
from pfe_validators_common import create_app

app = create_app(
    "check-todos",
    "Report TODO/FIXME comments left in source code (PFE-IMPL-004).",
    check,
)
