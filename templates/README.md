# Templates

Project templates maintained with the practices of this repository, using
[copier](https://copier.readthedocs.io/).

| Template | Description |
| --- | --- |
| [`charm/`](charm/) | Kubernetes charm (ops, uv, tox, Terraform module, Sphinx docs, CI). Replaces `platform-engineering-charm-template`. |

## Create a project

Requires [uv](https://docs.astral.sh/uv/). Copier is run through `uvx`.

```shell
# Latest tagged version
uvx copier copy gh:canonical/platform-engineering ./my-charm

# From a local checkout of this repository (uncommitted changes are used)
uvx copier copy path/to/platform-engineering ./my-charm
```

Copier asks the questions defined in the template's `copier.yml`. To skip the prompts, pass
answers with `-d` (and `--defaults` for the remaining ones):

```shell
uvx copier copy --defaults \
  -d charm_name=my-service \
  -d title="My Service" \
  -d summary="Charm for My Service." \
  -d workload_container=my-service \
  -d workload_image=ghcr.io/canonical/my-service \
  -d workload_command="my-service --serve" \
  gh:canonical/platform-engineering ./my-charm
```

Copier needs `copier.yml` at the root of the repository, so the root `copier.yml` points
to `templates/charm/template` and includes the questions from `templates/charm/questions.yml`.
Use `--vcs-ref <tag>` to pin a released version. Without it, copier uses the latest tag.

After generation:

```shell
cd my-charm
uv lock          # the lock file is not shipped with the template
git init && git add . && git commit -m "chore: initial commit"
```

### Charm template questions

| Question | Description | Default |
| --- | --- | --- |
| `charm_name` | Charm name (lowercase, hyphens) | required |
| `title` | Charm title | derived from `charm_name` |
| `summary` | One-line summary | placeholder text |
| `repo_slug` | GitHub `org/name` for links | `canonical/<charm_name>` |
| `workload_container` | Workload container name | `workload` |
| `workload_image` | Upstream OCI image | `kennethreitz/httpbin` |
| `workload_command` | Pebble service command | httpbin example |

The Terraform module and the Sphinx docs are always included.

## Update an existing project

The answers are saved in `.copier-answers.yml` in the generated project, so it can pull
template changes:

```shell
uvx copier update
```

Commit `.copier-answers.yml` and do not edit it by hand.

## Contribute to a template

- Files that need substitution end with `.jinja`; every other file is copied as is
  (so GitHub Actions `${{ }}` expressions do not need escaping).
- Template sources live in `templates/<name>/template/` and questions in
  `templates/<name>/questions.yml`. They are excluded from the
  repository linters; they are validated by rendering them in CI.
- Changing a template is part of a practice change, see [CONTRIBUTING.md](../CONTRIBUTING.md).
