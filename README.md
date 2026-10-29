# Platform Engineering

Public resources of the Canonical Platform Engineering team: engineering
practices, the agent skills and validators that support them, and the
templates we start new projects from.

Rather than copy-pasting (and slowly diverging) the same guidance across every
repository, we keep the source of truth here and either link to it or consume
it directly.

## What is in this repository

* **Practices** ([`src/`](src), [`CONTRIBUTING.md`](CONTRIBUTING.md),
  [`catalog.yaml`](catalog.yaml)): the engineering practices the team expects
  of each other. Each practice has a stable ID (`PFE-<AREA>-<NNN>`) that links
  it to its documentation, skills and validators. The practices will move to
  [`docs/`](docs) when the Read the Docs site is configured.
* **Skills** ([`skills/`](skills)): agent skills that help apply the practices.
* **Validators** ([`validators/`](validators)): compliance checks usable from
  GitHub workflows and from the command line.
* **Actions** ([`actions/`](actions)): reusable GitHub Actions that are not
  validators.
* **Templates** ([`templates/`](templates)): index of the templates for new
  projects, such as the charm template.

*The practices are under development.* Changes can be proposed by anyone
through pull requests, including to anything in this repository.

## Repository layout

```text
.
├── catalog.yaml          # practice IDs -> doc, skills, validators
├── src/                  # practices documentation sources
├── CONTRIBUTING.mdt      # template rendered into CONTRIBUTING.md
├── docs/                 # placeholder for the Read the Docs site
├── skills/<name>/        # agent skills (SKILL.md + optional scripts/)
├── validators/<name>/    # one Python package + action.yml per validator
├── validators/_template/ # starting point for a new validator
├── packages/             # shared libraries (pfe-validators-common)
├── actions/<name>/       # non-validator GitHub Actions
├── templates/            # index of project templates (live in their own repos)
├── tools/                # repository maintenance (catalog check)
└── .github/workflows/    # CI and the reusable compliance.yaml workflow
```

The Python code is a [uv workspace][uv-workspace]: each validator is an
independent package, and all of them share `packages/pfe-validators-common`, a
single lockfile and a single development virtual environment.

[uv-workspace]: https://docs.astral.sh/uv/concepts/projects/workspaces/

## Using the validators

Each validator under `validators/<name>` can be used in three ways. Pin a
release tag (`@v1`, `@v1.2.0`) rather than `main`.

### Command line with uvx

```shell
uvx --from 'git+https://github.com/canonical/platform-engineering@v1#subdirectory=validators/check-todos' \
  check-todos .
```

All validators share the same interface: `<name> [--format text|github|json]
[PATH ...]`, exiting with `0` (compliant), `1` (findings) or `2` (error).

### GitHub Action

```yaml
steps:
  - uses: actions/checkout@v7
  - uses: canonical/platform-engineering/validators/check-todos@v1
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

The structure of the practices in `CONTRIBUTING.md` is:

* Each line is limited to 100 characters for readability
* The content index is sorted alphabetically to facilitate quickly looking up a
  standard
* Optionally, headings can be used to aggregate similar standards
* Standards should be grouped together for readability when similar, which
  means in the body, they do not have to be sorted alphabetically
* Each standard has the structure:
  * a heading with a name of the standard,
  * a description of the problem it intends to address,
  * the standard and
  * an explanation of how the standard addresses the problem.

Adding a standard to `src/` requires an entry in `catalog.yaml`. To render
`CONTRIBUTING.md`, run `python3 scripts/render.py > CONTRIBUTING.md`.

### Development

```shell
uv sync                         # create the workspace virtual environment
uv run pytest                   # run all tests
uv run ruff check && uv run ruff format --check
uv run mypy
uv run tools/check_catalog.py   # validate catalog.yaml references
```

See [AGENTS.md](AGENTS.md) for the conventions used when adding validators,
skills and actions.
