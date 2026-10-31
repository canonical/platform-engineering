# Contributing

## Skill first

Every action that has to be repeated on more than 5 repositories must have a skill.

A pull request MUST be opened on this repository with:

1. **A doc, spec or KB entry** with the context and the team contact.
2. **A validator** checking whether a repository is compliant.
   - The first version does not have to be complete.
   - Validators are versioned (see [Versioning validators](#versioning-validators)).
   - Validators can be run with `uvx` on any repository.
3. **A skill** to execute the work.
   - It may just be a one-line prompt.
   - Skills are versioned.
4. **A charmkeeper recipe** to apply the skill on multiple repositories.

## Development setup

Requirements: [uv](https://docs.astral.sh/uv/), [just](https://just.systems/) and Node.js
(for markdownlint, via `npx`).

```shell
just lint   # all linters
just fmt    # auto-format Python
just test   # validator tests
```

## Conventions

- Skills: `skills/<name>/SKILL.md` with `name` and `description` front matter.
  `name` must match the folder name.
- Knowledge base: `kb/<topic>.md` with a `title` and `owner` front matter.
- Validators: one package per validator in `validators/<name>/` (a member of the uv workspace
  in `validators/pyproject.toml`), with its own `pyproject.toml`, a console script and tests.
- Use [conventional commits](https://www.conventionalcommits.org/).

## Versioning validators

Each validator has its own [semver](https://semver.org/) version: `[project].version` in its
`pyproject.toml`. Releases are git tags named `<validator>/v<version>`, for example
`terraform-compliance/v0.1.0`.

- If a PR changes a validator's code (`src/`, `pyproject.toml` or its dependencies), it MUST bump
  the version, and run `uv lock` in `validators/`. CI blocks the PR otherwise.
- On merge to `main`, CI creates the tag and a GitHub release for any version that has no tag yet.
- Tags are immutable; never reuse a version.
