# Platform Engineering

Public resources of the Canonical Platform Engineering team: engineering
practices, the agent skills and validators that support them, and the
templates we start new projects from.

Rather than copy-pasting (and slowly diverging) the same guidance across every
repository, we keep the source of truth here and either link to it or consume
it directly.

## What is in this repository

* **Practices** ([`src/`](src)): the engineering practices the team expects of
  each other, one page per practice grouped by area. They will move to
  [`docs/`](docs) when the Read the Docs site is configured.
* **Skills** ([`skills/`](skills)): agent skills that help apply the practices.
* **Compliance** ([`compliance/`](compliance)): validators that check the
  practices, usable from GitHub workflows and from the command line.
* **Actions** ([`actions/`](actions)): reusable GitHub Actions that are not
  validators.
* **Templates** ([`templates/`](templates)): templates for new projects, such
  as the charm template.

*The practices are under development.* Changes can be proposed by anyone
through pull requests, including to anything in this repository.

## Repository layout

```text
.
├── src/                          # practices documentation
├── docs/                         # placeholder for the Read the Docs site
├── skills/<name>/                # agent skills (SKILL.md + optional scripts/)
├── compliance/
│   ├── common/                   # shared library (pfe-validators-common)
│   └── validators/
│       ├── <name>/               # one Python package (+ action.yml)
│       └── _template/            # starting point for a new validator
├── actions/<name>/               # non-validator GitHub Actions
├── templates/
│   └── charm/                    # charm template (platform-engineering-charm-template)
└── .github/workflows/            # CI and the reusable compliance.yaml workflow
```

The Python code is a [uv workspace][uv-workspace]: each validator is an
independent package, and all of them share `compliance/common`, a single
lockfile and a single development virtual environment.

[uv-workspace]: https://docs.astral.sh/uv/concepts/projects/workspaces/

## Using the validators

Each validator under `compliance/validators/<name>` can be used in three
ways. Pin a release tag (`@v1`, `@v1.2.0`) rather than `main`.

### Command line with uvx

```shell
uvx --from 'git+https://github.com/canonical/platform-engineering@v1#subdirectory=compliance/validators/check-todos' \
  check-todos .
```

All validators share the same interface: `<name> [--format text|github|json]
[PATH ...]`, exiting with `0` (compliant), `1` (findings) or `2` (error).

### GitHub Action

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: canonical/platform-engineering/compliance/validators/check-todos@v1
```

### Reusable workflow

```yaml
jobs:
  compliance:
    uses: canonical/platform-engineering/.github/workflows/compliance.yaml@v1
    with:
      ref: v1   # keep in sync with the @ref above
      validators: '["check-todos"]'
```

## Using the skills

Skills follow the [Agent Skills](https://agentskills.io) format. Copy or
symlink `skills/<name>/` into your agent's skills directory, for example
`~/.agents/skills/`.

## Contributing

Each practice page in `src/` has the structure:

* a heading with the name of the practice,
* a description of the problem it intends to address,
* the practice and
* an explanation of how the practice addresses the problem.

### Development

```shell
uv sync                         # create the workspace virtual environment
uv run pytest                   # run all tests
uv run ruff check && uv run ruff format --check
uv run mypy
```

See [AGENTS.md](AGENTS.md) for the conventions used when adding validators,
skills and actions.
