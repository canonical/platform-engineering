# Agent guidelines

Conventions for humans and agents contributing to this repository. See
[README.md](README.md) for the layout and how each part is consumed.

## Practices

* One page per practice under `src/<area>/`, following the structure
  described in [README.md](README.md).
* A validator or skill names the practice page it relates to in its README.

## Validators

* One validator per directory under `compliance/validators/`, named
  `check-<topic>`. The directory name, the package name and the console
  script are identical, so
  `uvx git+...#subdirectory=compliance/validators/<name>` works without
  `--from`.
* Start from
  [`compliance/validators/_template`][template].
* Python only, standard library first. Shared code goes to
  `compliance/common` instead of being copied.
* Use `run_cli()` so every validator has the same interface and exit codes,
  and tag every `Finding` with a practice ID (`PFE-<AREA>-<NNN>`).
* Each validator ships `pyproject.toml`, `action.yml` (composite action
  running `uvx --from "${{ github.action_path }}"`), `README.md`, and
  `tests/` with good and bad fixtures.
* Add a self-test job in `.github/workflows/actions-selftest.yaml`.
* Validators that inspect a developer machine rather than repository files
  (for example `check-devenv`) ship no `action.yml` and are used with `uvx`
  only.

## Skills

* One skill per directory under `skills/`, with a `SKILL.md` whose
  frontmatter has `name` (matching the directory) and `description`.
* Skills point to the documentation and validators rather than duplicating
  the practice text.

## Checks before proposing a change

```shell
uv sync --locked
uv run ruff check && uv run ruff format --check
uv run mypy
uv run pytest
```

New Markdown must pass `mdl` with the repository `.mdlrc` (80-column lines,
code blocks excepted).

[template]: compliance/validators/_template/README.md
