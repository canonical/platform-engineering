---
title: Upgrading a 12-factor app from paas-charm 1.x to 2.0
owner: Platform Engineering
---

Upgrading a 12-factor app from `paas-charm` 1.x to 2.0 is a manual migration, not a version
bump. `paas-charm` 2.0 is only supported on the Ubuntu 26.04 LTS base: a charm or rock that
keeps an Ubuntu 22.04 LTS or Ubuntu 24.04 LTS base stays on `paas-charm` 1.x, and repacking it
is not an upgrade path. Every rock and charm must be migrated and rebuilt before a deployment
is refreshed.

Authoritative upstream sources:

- [`paas-charm` 2.0 release notes](https://documentation.ubuntu.com/paas-charm/latest/release-notes/)
- [How to upgrade](https://documentation.ubuntu.com/paas-charm/latest/how-to/upgrade/)
- [`paas-config.yaml` reference](https://documentation.ubuntu.com/paas-charm/latest/reference/paas-config/)
- [Custom relations reference](https://documentation.ubuntu.com/paas-charm/latest/reference/custom-relations/)
- [uv plugin migration](https://documentation.ubuntu.com/paas-charm/latest/how-to/uv-migration/)

## Breaking changes

### Bases

| Artifact | 1.x | 2.0 |
| --- | --- | --- |
| Charm | `base: ubuntu@22.04` or `ubuntu@24.04` | `base: ubuntu@26.04` |
| Rock | `base: ubuntu@22.04` or `ubuntu@24.04` | `base: ubuntu@26.04`, or `base: bare` with `build-base: ubuntu@26.04` |

Ubuntu 26.04 LTS framework charms default to `charm-user: non-root`.

### Workload container and resource names

Flask and Django rename the workload container and OCI resource:

| 1.x | 2.0 |
| --- | --- |
| `flask-app` / `flask-app-image` | `app` / `app-image` |
| `django-app` / `django-app-image` | `app` / `app-image` |

FastAPI, ExpressJS, Go and Spring Boot already used `app` / `app-image`. Every `juju deploy`,
`juju refresh`, Terraform module, bundle, overlay and CI job that passes `--resource` must be
updated.

> **Flask and Django:** on Juju earlier than 4.1 the container rename cannot be applied with
> `juju refresh`. The old container stays alive and the refresh fails
> ([LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955)). Remove the application with
> `juju remove-application` and redeploy the new charm instead.

### Workload paths

- The application root is `/app` for **all** frameworks. Flask's `/flask` and Django's `/django`
  are gone.
- `gunicorn.conf.py` moves to `/var/lib/gunicorn` (Flask and Django).
- Charm state (migration status, original Pebble services) moves to `/tmp/paas-charm`. Rocks no
  longer provide `/app/state`.
- All framework rocks provide `/app-data`, writable by the `_daemon_` user.
- Rockcraft extension part names use `.` instead of `/` when the effective build base is
  Ubuntu 26.04 LTS: `flask-framework/dependencies` becomes `flask-framework.dependencies`.
- Entries in `parts.install-app.prime` must start with `app`: `flask/app/app.py` becomes
  `app/app.py`.

### Dependency management

The `uv` plugin is the default and the `charm` plugin is not supported. Charms declare
dependencies in `pyproject.toml` with a committed `uv.lock`; `requirements.txt` is deleted and
`charm-strict-dependencies` is removed. `paas-charm` 2.0 requires Python 3.12 or greater and
pins its own `ops`, `pydantic`, `jsonschema`, `cosl` and `dpcharmlibs-interfaces` versions, so
the charm must not pin older ones.

With a framework extension on Ubuntu 26.04 LTS, Charmcraft generates `parts.charm`; declaring
it manually fails the pack with "incompatible with customized charm part". The extension also
stages `paas-config.yaml` automatically, so no `dump` part is needed.

### Charm contract

- The `secret-storage` peer relation and interface are renamed to `peers`.
- `flask-secret-key`, `django-secret-key`, the string `app-secret-key` and `app-secret-key-id`
  are replaced by one `app-secret-key` option of `type: secret` that takes a Juju user secret ID.
  A fresh key is generated on upgrade, which invalidates existing signed sessions.
- The application port is read only from `port` in `paas-config.yaml`. The `app-port`,
  `webserver-port`, `metrics-port` and `metrics-path` config options are gone.
- Redis is replaced by Valkey: the `valkey` endpoint and `VALKEY_DB_*` variables.
- The `paas_app_charmer` import path is removed; use `paas_charm`.
- `charms.hydra.v0.oauth`, the OpenFGA and tracing Charmhub libraries are replaced by the
  `charmlibs-interfaces-oauth`, `charmlibs-interfaces-openfga` and `charmlibs-interfaces-tracing`
  Python dependencies. `loki_push_api` must be v1.
- Tracing uses `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` and
  `OTEL_EXPORTER_OTLP_TRACES_PROTOCOL=http/protobuf`; the generic `OTEL_EXPORTER_OTLP_ENDPOINT`
  is no longer set.

## New capabilities to adopt

### `paas-config.yaml`

The charm-owned, build-time `paas-config.yaml` sits next to `charmcraft.yaml`. Top-level keys:

| Key | Purpose |
| --- | --- |
| `port` | Application server port (framework default otherwise). |
| `metrics-port` | Port the workload serves metrics on. |
| `metrics-path` | Slash-prefixed HTTP path for metrics. |
| `framework_logging_format: json` | Structured framework logs (Flask, Django, FastAPI only). |
| `prometheus.scrape_configs` | Extra scrape jobs, appended to the framework job. |
| `config.options` | Rename environment variables generated from config options and secrets. |

`config.options` entries use exactly one of `env-var` (plain option) or `secret-env-vars`
(option of `type: secret`). Mappings replace default names rather than adding aliases, apply to
defaults, and have the highest precedence in the workload environment. Sources must be options
declared in `charmcraft.yaml`; settings that only exist in `paas-config.yaml`, such as `port`,
cannot be mapping sources.

Invalid `paas-config.yaml` fails the hook at runtime, so validate it before packing.

### Custom relations

`paas_charm.relations` is the public, stable extension API. A `CustomRelation` subclass
implements `setup(on_change)` (required), `ensure_ready()` and `gen_environment()`, and is
registered through the charm's `custom_relations` class attribute. The framework injects a
read-only `Context` (`app_name`, `framework_name`, `port`, `container_name`, resolved `config`)
and a required flag read from the endpoint's `optional` field in `charmcraft.yaml`.

Hand-rolled relation handling in `src/charm.py` — observing `relation_*` events directly and
pushing variables into the workload — must move into a `CustomRelation`. A custom relation that
is not listed under `requires` aborts the charm at startup. `optional` defaults to `false`, so a
relation that the app can run without must set `optional: true` explicitly.

Relation environment precedence, lowest to highest: charm config and framework settings, then
built-in relations and Prometheus metrics, then custom relations in registration order, then
explicit `config.options` mappings.

## Tooling

Until Ubuntu 26.04 LTS framework support leaves experimental status:

```shell
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack
CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 charmcraft pack
```

The 2.0 charm contract (`peers`, secret-typed `app-secret-key`, `charmcraft init --base`) is
only generated by the `latest/edge` Charmcraft snap. Rockcraft 1.21 or later is required.

## Checking compliance

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@paas-charm-v2/v<version>#subdirectory=validators/paas-charm-v2" \
  paas-charm-v2 <path-to-repo>
```

See [`validators/paas-charm-v2`](../validators/paas-charm-v2/README.md) for the checks, and
[`skills/12factor-v2-upgrade`](../skills/12factor-v2-upgrade/SKILL.md) for the migration skill.
