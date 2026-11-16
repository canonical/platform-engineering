# paas-charm-v2

Checks whether a 12-factor app repository complies with the `paas-charm` 2.0 contract on the
Ubuntu 26.04 LTS base. Rules are taken from the
[`paas-charm` 2.0 release notes](https://documentation.ubuntu.com/paas-charm/latest/release-notes/)
and the "Upgrade to `paas-charm` 2.0" how-to guide.

Layout (`src/paas_charm_v2/`):

- `project.py`: discovery of charm and rock project directories, and file loading.
- `paas_config.py`: schema validation for the charm-owned `paas-config.yaml`.
- `check.py`: the checks and CLI.

## Usage

Requires Python >= 3.11.

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@paas-charm-v2/v<version>#subdirectory=validators/paas-charm-v2" \
  paas-charm-v2 /path/to/repo
```

Exit codes: `0` pass, `1` violations found, `2` no directories given or bad arguments.
Flags: `--verbose`, `--check <slug>`, `--list-checks`.

## What it checks

| Slug | Checks |
| --- | --- |
| `charm-base` | `charmcraft.yaml` declares `base: ubuntu@26.04` and not the legacy `bases` key. |
| `rock-base` | `rockcraft.yaml` uses `base: ubuntu@26.04`, or `base: bare` with `build-base: ubuntu@26.04`. Extension part names use `.` instead of `/`, `install-app` prime entries start with `app`, and no `/flask`, `/django` or `/app/state` paths remain. |
| `uv-plugin` | `parts.charm` uses `plugin: uv` with the `astral-uv` build snap and no `charm-strict-dependencies`; `pyproject.toml` and `uv.lock` exist and `requirements.txt` is gone. |
| `paas-charm-pin` | `project.dependencies` pins `paas-charm` to 2.x only (`==2.0`, `==2.0.*`, `>=2,<3`, `>=2.0.dev1,<3`), and `requires-python` is at least 3.12. |
| `workload-container` | The workload container is `app` with the `app-image` resource (`flask-app`/`django-app` were renamed). |
| `paas-config` | `paas-config.yaml` parses and matches the 2.0 schema: known top-level keys, valid `port`/`metrics-port`/`metrics-path`, supported `framework_logging_format`, well-formed `prometheus.scrape_configs`, and `config.options` mappings that name declared options, use exactly one of `env-var`/`secret-env-vars` and have unique destinations. |
| `custom-relations` | Non-built-in `requires` endpoints are backed by a `paas_charm.relations.CustomRelation`, every `CustomRelation` is declared under `requires`, relation events are not observed directly in `src/`, no `paas_app_charmer` imports remain, and `redis` is replaced by `valkey`. |
| `charm-contract` | The `peers` relation replaces `secret-storage`, `app-secret-key` is `type: secret`, retired options (`app-secret-key-id`, `flask-secret-key`, `django-secret-key`, `app-port`, `webserver-port`, `metrics-port`, `metrics-path`) are gone, and the deprecated `loki_push_api` v0 and `hydra` libraries are not fetched. |

## Known deviations

- `paas-config.yaml` is optional, so a repository without one is reported as a skipped check
  rather than a violation.
- Hand-coded integration detection is a heuristic over `src/**/*.py`: it flags direct
  `relation_*` event observation in modules that do not use `custom_relations`.
- Framework detection reads the Charmcraft `extensions` key, then config option prefixes, then
  the rock extension. Checks that need a framework are skipped when it cannot be determined.
- Charmcraft and Rockcraft are not invoked; only the project files are read.

## Development

```shell
uv run --project validators --all-packages pytest validators/paas-charm-v2
```
