# Preface

How to add and maintain a validator in this repository.

IMPORTANT: Read the `.kb/agents.md` file.


# Laws

## §1 - One package per validator

Create `validators/<name>/` with `pyproject.toml`, `src/<package>/`, `tests/` and `README.md`, then add `<name>` to `[tool.uv.workspace].members` in `validators/pyproject.toml`.

## §2 - Expose a uvx-callable command

Define the console script in `[project.scripts]` so the validator can be run from any repository with `uvx --from "git+https://github.com/canonical/platform-engineering@<name>/v<version>#subdirectory=validators/<name>" <script> <path>`.

## §3 - Version and lock

Keep `[project].version` in semver. Any change to `src/`, `pyproject.toml` or dependencies MUST bump the version and run `uv lock --project validators`. Releases are immutable tags named `<name>/v<version>`.

## §4 - Test the validator

Add unit tests under `tests/` and run them with `uv run --project validators --all-packages pytest validators/<name>`.


# Concepts

## Layout

```text
validators/<name>/
├── README.md
├── pyproject.toml
├── src/<package>/
│   ├── __init__.py
│   └── ...
└── tests/
    └── test_<name>.py
```

Use [`terraform-compliance`](../terraform-compliance/) or
[`validate-jira-sync-config`](../validate-jira-sync-config/) as a starting point.

## Checklist

1. Create the package with a `hatchling` build backend, a `src/` layout and a console script.
2. Add Canonical copyright headers and Google-style docstrings; `just fmt` and `just lint` enforce the Python style.
3. Add unit tests for the checks and the command line exit codes.
4. Register the validator in `validators/pyproject.toml` and in the table in `validators/README.md`.
5. Run `uv lock --project validators`.
6. Run `just fmt`, `just lint` and `just test`.
7. If the validator supports a new practice, also add or update the matching KB entry, skill and charmkeeper recipe.
