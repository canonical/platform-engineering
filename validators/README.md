# Validators

`uvx`-callable scripts that check whether a repository complies with a practice.
Validators are versioned and the first version does not have to be complete.

This folder is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).
Each validator is a member with its own `pyproject.toml`, console script and tests:

```text
validators/
  pyproject.toml          # workspace root (dev tools only)
  <name>/
    pyproject.toml
    src/<package>/
    tests/
```

To add a validator, create the folder and add it to `members` in `validators/pyproject.toml`.

| Validator | Description |
| --- | --- |
| [`check-structure`](check-structure/) | Skills and KB front matter |
