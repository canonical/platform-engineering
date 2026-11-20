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
| `rock-base` | `rockcraft.yaml` uses `base: ubuntu@26.04`, or `base: bare` with `build-base: ubuntu@26.04`. Extension part names use `.` instead of `/`, `install-app` prime entries start with `app`, and no `/flask`, `/django` (including bare paths such as `working-dir: /flask`) or `/app/state` paths remain. A Flask or Django `<framework>-framework.dependencies` part that sets its own `override-build` must still write `.gunicorn-constraints.txt`, because the override replaces the extension's. |
| `uv-plugin` | `parts.charm` uses `plugin: uv` with the `astral-uv` build snap and no `charm-strict-dependencies`; `pyproject.toml` and `uv.lock` exist and `requirements.txt` is gone. |
| `paas-charm-pin` | `project.dependencies` pins `paas-charm` to 2.x only (`==2.0`, `==2.0.*`, `>=2,<3`, `>=2.0b1,<3`), the charm's `uv.lock` resolves `paas-charm` to 2.x, and `requires-python` is set and at least 3.14 (the Python of Ubuntu 26.04 LTS). |
| `workload-container` | The `app` workload container is declared with the `app-image` resource (`flask-app`/`django-app` were renamed). |
| `paas-config` | Every charm has a `paas-config.yaml` that sets `port`, `metrics-port` and `metrics-path` explicitly (framework defaults are fine), so docs have a real file to point at. The file parses and matches the 2.0 schema: known top-level keys, valid `port`/`metrics-port`/`metrics-path`, supported `framework_logging_format`, well-formed `prometheus.scrape_configs`, and `config.options` mappings that name declared options, match the option type (`secret-env-vars` for `secret` options, `env-var` otherwise), use exactly one of `env-var`/`secret-env-vars` and have unique destinations. |
| `custom-relations` | Non-built-in `requires` endpoints are backed by a `paas_charm.relations.CustomRelation`, every `CustomRelation` is declared under `requires`, relation events are not observed directly in `src/`, no `paas_app_charmer` imports remain, and `redis` is replaced by `valkey`. |
| `charm-contract` | The `peers` peer relation exists and replaces `secret-storage`, `app-secret-key` is declared with `type: secret`, retired options (`app-secret-key-id`, `flask-secret-key`, `django-secret-key`, `app-port`, `webserver-port`, `metrics-port`, `metrics-path`) are gone, and the deprecated `loki_push_api` v0 and `hydra` libraries are not fetched. |
| `charm-hooks` | The charm does not call `super()._on_config_changed` or `super()._on_pebble_ready`, or define those methods without observing them. `paas-charm` 2.0 removed them (pylint `no-member`, and the override silently never runs); override `_reconcile(self, rerun_migrations=False)` instead. |
| `repo-ci` | CI configuration still works after the migration: `.licenserc.yaml` (or `.licenserc.yml`) `header.paths-ignore` covers the generated `uv.lock` (the lock next to the charm's `charmcraft.yaml`, matched as a glob; `uv.lock` files elsewhere in the repository belong to other projects and are ignored), and `tox.ini`, `pyproject.toml`, `Makefile`, `noxfile.py`, `justfile` and `.github/workflows/*.y*ml` do not reference the deleted `requirements.txt`. |
| `upgrade-docs` | Flask and Django only. A Markdown upgrade guide states the problem affects Juju earlier than 4.1, mentions Juju bug [LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955) and `juju remove-application` (the container rename keeps the old container alive and fails `juju refresh`, so the charm must be removed and redeployed), and the changelog or release notes mention the same bug and the remove-and-redeploy step. |

## Known deviations

- `paas-charm` treats `paas-config.yaml` as optional, but the validator requires it with `port`,
  `metrics-port` and `metrics-path` set, so the effective values are visible and documentable.
- Hand-coded integration detection is a heuristic over `src/**/*.py`: it flags direct
  `relation_*` event observation in modules that do not use `custom_relations`.
- Framework detection reads the Charmcraft `extensions` key, then config option prefixes, then
  the rock extension. Checks that need a framework are skipped when it cannot be determined.
- Charmcraft and Rockcraft are not invoked; only the project files are read.

## Development

```shell
uv run --project validators --all-packages pytest validators/paas-charm-v2
```
