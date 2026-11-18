---
name: 12factor-v2-upgrade
description: >
  Upgrades a Canonical 12-factor app repository from paas-charm 1.x to 2.0: moves the charm and
  every rock to the Ubuntu 26.04 LTS base, renames the Flask and Django workload container and
  OCI resource to app and app-image, relocates workload paths under /app, converts the charm to
  the uv plugin with a pinned paas-charm 2.x dependency, moves hand-coded relations into
  CustomRelation classes, adopts paas-config.yaml, and validates the result.
  WHEN: upgrade paas-charm, migrate to paas-charm 2.0, paas-charm v1 to v2, 12-factor Ubuntu
  26.04 migration, bump charm or rock base to 26.04, rename flask-app container to app, rename
  django-app-image, migrate charm plugin to uv plugin, pin paas-charm 2.x, create
  paas-config.yaml, convert integration to CustomRelation, replace secret-storage with peers,
  replace redis with valkey, fix flask-secret-key app-secret-key, run paas-charm-v2 validator.
license: Apache-2.0
metadata:
  author: Canonical Platform Engineering
  version: "1.0.0"
  summary: Migrates a 12-factor charm and its rocks from paas-charm 1.x to 2.0 on Ubuntu 26.04 LTS, then validates the result.
  tags:
    - 12-factor
    - paas-charm
    - charm
    - rock
    - migration
---

# Upgrade a 12-factor app to paas-charm 2.0

## Overview

`paas-charm` 2.0 only runs on the Ubuntu 26.04 LTS base. Repacking a 22.04 or 24.04 project
keeps it on `paas-charm` 1.x, so this is a manual migration of every rock and charm in the
repository, not a version bump. Use this skill to perform that migration end to end and leave
the repository compliant with the [`paas-charm-v2` validator](../../validators/paas-charm-v2/README.md).

Background and the full list of breaking changes: [`kb/12factor-v2-upgrade.md`](../../kb/12factor-v2-upgrade.md).

To run this migration across many repositories at once, launch the CharmKeeper campaign recipe
[`charmkeeper.yaml`](charmkeeper.yaml), which sits next to this file and installs this skill.

## Before starting

Confirm with the user, and stop if the answer rules the upgrade out:

1. **Is this a 12-factor app?** The repository has a `charmcraft.yaml` using a
   `*-framework` extension (`django`, `expressjs`, `fastapi`, `flask`, `go`, `spring-boot`).
   If not, this skill does not apply.
2. **Can the deployment take a session reset?** The application secret key is regenerated on
   upgrade, signing out users of Flask, Django, FastAPI, ExpressJS and Spring Boot apps unless a
   Juju user secret is supplied.
3. **Flask or Django only: can the charm be removed and redeployed?** Their workload container
   is renamed `flask-app`/`django-app` → `app`. Juju 3.x and 4.0 have a bug
   ([LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955)) that keeps the old container
   alive and fails `juju refresh`, so these charms cannot be refreshed in place: they must be
   removed with `juju remove-application` and redeployed with the new version. Confirm the
   deployment can lose and recreate its integrations, config and any stored data.
4. **Is the tooling available?** Rockcraft 1.21+, the `latest/edge` Charmcraft snap (stable
   generates the old contract), `uv`, and Python 3.12+.

## Workflow

Run the steps in order. Re-run the validator after each phase.

### Step 0: Baseline

```shell
uvx --from "git+https://github.com/canonical/platform-engineering@paas-charm-v2/v<version>#subdirectory=validators/paas-charm-v2" \
  paas-charm-v2 . --verbose
```

Record the failing checks. They are the task list; the validator is the definition of done.

Also inventory, by reading the repository:

- every `rockcraft.yaml` and its framework extension;
- the charm's `requires`, `provides` and `peers` endpoints, and which are built-in
  (`ingress`, `logging`, `postgresql`, `mysql`, `mongodb`, `valkey`, `s3`, `saml`, `rabbitmq`,
  `tracing`, `smtp`, `openfga`, `oidc`, `http-proxy`) versus author-owned;
- relation handling, Pebble layers and environment plumbing in `src/`;
- every place that names the OCI resource: Terraform, bundles, overlays, CI, scripts, tests,
  docs.

### Step 1: Migrate the rocks

For each `rockcraft.yaml`:

- Set `base: ubuntu@26.04`, or keep `base: bare` and set `build-base: ubuntu@26.04` for a
  chiselled rock.
- Rename extension-generated parts from `/` to `.`:
  `flask-framework/dependencies` → `flask-framework.dependencies`. Update `after:` references,
  selectors, scripts, patches and CI assertions that name them. Not every generated part exists
  for every framework: compare against `rockcraft expand-extensions` rather than renaming blindly.
- Prefix `parts.install-app.prime` entries with `app`: `flask/app/app.py` → `app/app.py`.
- Replace framework-specific paths with `/app` (Flask's `/flask`, Django's `/django`), including
  `working-dir` of custom services such as Celery workers and schedulers.
- Delete anything providing `/app/state` or `/tmp/<framework>/state`; the charm creates
  `/tmp/paas-charm` itself.
- Point writable application data at `/app-data`, owned by `_daemon_`.
- For Flask and Django, expect `gunicorn.conf.py` under `/var/lib/gunicorn`.
- Bump `version` so Kubernetes does not serve a cached image.
- If a Flask or Django rock overrides `override-build` on `<framework>-framework.dependencies`,
  the override replaces the extension's, which writes `.gunicorn-constraints.txt`. Add
  `printf '%s\n' 'gunicorn~=26.0' > .gunicorn-constraints.txt` before `craftctl default`, or
  `rockcraft pack` fails with "Could not open requirements file: .gunicorn-constraints.txt".

Verify the expanded project before packing:

```shell
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft expand-extensions
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack
```

### Step 2: Generate the new charm project

`charmcraft init` never overwrites files, so generate into a sibling directory and migrate into
it. Do **not** run it in the existing charm directory.

```shell
mkdir charm-26-04 && cd charm-26-04
CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 \
  charmcraft init --profile <FRAMEWORK>-framework --base ubuntu@26.04
```

Keep every generated declaration: `base: ubuntu@26.04`, the platforms, `charm-user: non-root`,
`parts.charm` with the `uv` plugin, the `app` container, the `app-image` resource, the `peers`
peer relation, the secret-typed `app-secret-key` option, the `paas-charm>=2.0b1,<3` dependency
and the `charmlibs` interface dependencies.

Carry forward only application-specific work: charm source and tests, extra config options,
actions, author-owned relations, charm libraries, custom parts and application Python
dependencies. Never replace a generated file wholesale with its 1.x counterpart.

Do not redeclare `app-secret-key` and do not add a `dump` part for `paas-config.yaml`: the
extension provides both. Declaring `parts.charm` alongside an extension fails the pack.

### Step 3: Finish the uv migration

- Delete `requirements.txt`; its dependencies move to `project.dependencies` in `pyproject.toml`.
- Set `requires-python = ">=3.12"`.
- Pin `paas-charm` to 2.x only: `paas-charm>=2.0b1,<3`.
- Remove pins of `ops`, `pydantic`, `jsonschema`, `cosl` and `dpcharmlibs-interfaces` unless the
  charm's own code needs them; `paas-charm` 2.0 pins its own versions and older pins make
  `uv lock` fail.
- Keep the empty `charmlibs-pydeps` dependency group if the generated project has one.
- Generate and commit the lock file; `charmcraft pack` fails without it.

```shell
uv lock
```

- Keep CI working: the charm's `uv.lock` (next to `charmcraft.yaml`; other `uv.lock` files in the repository are unrelated) has no license header and no comment style, so add its path to
  `header.paths-ignore` in `.licenserc.yaml` (skywalking-eyes fails otherwise), and replace every
  reference to the deleted `requirements.txt` in `tox.ini`, `pyproject.toml`, `Makefile` and
  workflows (for example `-r{toxinidir}/charm/requirements.txt`) with `paas-charm>=2.0b1,<3`
  or the dependency group.

### Step 4: Apply the contract renames

| 1.x | 2.0 |
| --- | --- |
| `flask-app` / `django-app` container | `app` |
| `flask-app-image` / `django-app-image` resource | `app-image` |
| `secret-storage` peer relation and interface | `peers` |
| `flask-secret-key`, `django-secret-key`, `app-secret-key-id` | one `app-secret-key` of `type: secret` |
| `app-port`, `webserver-port`, `metrics-port`, `metrics-path` options | `port`, `metrics-port`, `metrics-path` in `paas-config.yaml` |
| `redis` endpoint, `REDIS_DB_*` | `valkey` endpoint, `VALKEY_DB_*` |
| `paas_app_charmer` imports | `paas_charm` |
| `charms.hydra.v0.oauth`, OpenFGA and tracing Charmhub libs | `charmlibs-interfaces-*` dependencies |
| `loki_push_api` v0 | `loki_push_api` v1 |

The resource rename is separate from the container rename: update `juju deploy --resource`,
`juju refresh --resource`, Terraform, bundles, overlays, CI/CD and test fixtures. Search the
whole repository for the old names, not just the charm directory.

For Flask and Django the container rename also breaks `juju refresh` on Juju 3.x and 4.0
([LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955)); see Step 7 and Step 8.

Tell the user to reapply any existing secret key as a Juju secret:

```shell
juju add-secret my-app-secret-key value=<secret-string>
juju grant-secret my-app-secret-key <app>
juju config <app> app-secret-key=secret:<secret id>
```

### Step 4b: Port overridden base-class hooks

`paas-charm` 2.0 removed `_on_config_changed` and `_on_pebble_ready` from the base charm. Every
event now routes through `_reconcile(self, rerun_migrations: bool = False)`. A 1.x override such
as `def _on_config_changed(...): ...; super()._on_config_changed(event)` fails pylint
(`E1101 no-member`) and, worse, silently never runs. Move the logic into:

```python
def _reconcile(self, rerun_migrations: bool = False) -> None:
    """Do the charm-specific work, then reconcile.

    Args:
        rerun_migrations: whether it is necessary to run the migrations again.
    """
    self._my_setup()
    super()._reconcile(rerun_migrations)
```

Update unit tests that called the old hooks. Search `src/` for `super()._on_` and for any other
private base-class members the charm relies on; confirm each still exists in `paas_charm`.

`_reconcile` runs on every event, including early hooks such as `peers-relation-created` and
`leader-elected`, so charm-specific work must be idempotent and must not assume the workload
container is ready: guard on `self._container.can_connect()`.

### Step 4c: Make charm code work as the non-root workload user

The 2.0 workload container runs Pebble as the non-root `_daemon_` user (home
`/var/lib/pebble/default`, writable app data in `/app-data`). Charm code that relied on root in
1.x fails at runtime, not at lint or unit-test time, and puts the unit into error (for example
`fork/exec /usr/bin/sh: operation not permitted`). Search `src/` for each of these and port it:

- `container.exec(..., user="root", group="root")`: drop `user`/`group`, or avoid the command by
  using `container.make_dir` and `container.push`.
- `container.push(..., user=..., group=...)` and `chown` in shell commands: remove them. Files
  are owned by the Pebble user, and `chown` to another user is not permitted.
- Writes under root-owned paths such as `/etc/...` (for example `/etc/ssh/ssh_config.d/`) and
  `/usr/...`: move them to a path the workload user owns, such as `~/.ssh/config` for SSH client
  settings or `/app-data`, and set the file mode explicitly (`0o600` for config and keys).
- Anything that assumed a specific user name or `chown`/`install -o` ownership.

Unit tests with a mocked container cannot catch this, so verify on a real deployment. Deploy the
packed charm with the relevant config set, then check the unit reaches `active` and inspect the
result in the workload container:

```shell
kubectl exec -n <model> <app>-0 -c app -- ls -la <path>
```

### Step 5: Move hand-coded integrations into custom relations

Any author-owned relation that is observed directly in `src/charm.py` — `self.framework.observe`
on `relation_created`/`changed`/`broken`, databag reads, manual environment injection or Pebble
restarts — becomes a `paas_charm.relations.CustomRelation` subclass. See
[`references/custom_relation_migration.md`](references/custom_relation_migration.md) for the
before/after pattern, the method-by-method mapping and the error semantics.

Rules that the validator enforces:

- Every non-built-in endpoint under `requires` must be claimed by a `CustomRelation` whose
  `relation_name` matches.
- Every `CustomRelation` must be declared under `requires`, or the charm aborts at startup.
- `optional` in `charmcraft.yaml` is the single source of truth for required versus optional. It
  defaults to `false`; set `optional: true` explicitly when the app runs without the relation.

Do not invent optionality: carry forward the behaviour the 1.x charm had, and confirm it with the
user when the old code was ambiguous.

### Step 6: Adopt `paas-config.yaml`

Create or extend `paas-config.yaml` next to `charmcraft.yaml`, and move settings that no longer
belong in `charmcraft.yaml` into it. See
[`references/paas_config_recipes.md`](references/paas_config_recipes.md) for the full schema,
framework defaults and worked examples.

Adopt, in this order of value:

1. `port` — required if the app does not listen on the framework default, because
   `app-port`/`webserver-port` no longer exist.
2. `metrics-port` and `metrics-path` — same reason, and they become the framework scrape job.
3. `prometheus.scrape_configs` — replaces any bespoke `prometheus_scrape` wiring in `src/`, for
   sidecar or worker metrics. Use the `@scheduler` placeholder for unit-0-only targets.
4. `framework_logging_format: json` — for Flask, Django and FastAPI only.
5. `config.options` — replaces code that renamed environment variables for the workload, and
   lets the workload keep the variable names it already reads instead of being changed.

Only add keys that the repository actually needs; every key is optional and omitted keys fall
back to framework defaults.

### Step 7: Validate, build and hand over

Run the repository's own CI checks locally before opening a PR; the validator does not replace
them. At minimum `tox run -e lint,unit` (pylint, flake8, mypy, black, isort, unit tests) and the
license header check configured in `.licenserc.yaml`. Fix findings in the migrated code rather
than suppressing them.

```shell
uv lock
uvx --from "git+https://github.com/canonical/platform-engineering@paas-charm-v2/v<version>#subdirectory=validators/paas-charm-v2" \
  paas-charm-v2 . --verbose
ROCKCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 rockcraft pack
CHARMCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS=1 charmcraft pack
```

Then replace the old charm directory with `charm-26-04` in one move, and give the user the
upgrade command.

**Flask and Django:** do not give a `juju refresh`. Because of
[LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955), remove the application and deploy
the new charm, then recreate integrations and config (including the `app-secret-key` secret).

Removing the application deletes its Juju configuration. Only when the charm declares config
options that deployments set to non-default values (anything under `config.options` in
`charmcraft.yaml` other than `app-secret-key`), tell the user to save those values before removal and restore them after redeployment, for example:

```shell
juju config <app> <option> > <option>.txt    # before removal, once per such option
juju config <app> <option>=@<option>.txt     # after redeployment
```

Also have them note the integrations (`juju status <app> --relations`) so they can be recreated
with `juju integrate`. If the charm has no such options and no integrations, omit this.

```shell
juju remove-application <app>
juju deploy ./<charm>_amd64.charm <app> --base ubuntu@26.04 \
  --resource app-image=<registry>/<rock>:<version>
```

**Other frameworks:** refresh in place:

```shell
juju refresh <app> --path ./<charm>_amd64.charm --base ubuntu@26.04 \
  --resource app-image=<registry>/<rock>:<version>
```

`--base ubuntu@26.04` is required so Juju picks the new charm. After the refresh or redeploy,
check `juju status` and the ingress and observability relations.

### Step 8: Document the upgrade (Flask and Django)

Update the repository's documentation; the `upgrade-docs` check of the validator enforces it:

- The upgrade how-to guide states that the container rename breaks `juju refresh` on Juju 3.x
  and 4.0 ([LP#1991955](https://bugs.launchpad.net/juju/+bug/1991955)), gives the
  `juju remove-application` and redeploy steps, and mentions the application secret key reset.
- Only when the charm declares config options (see Step 7), the guide
  also tells operators to save those option values and the integrations before removing the
  application, and to restore them after redeploying. Name the actual options, for example
  `files`. Skip this when the charm has no such options and no integrations.
- The changelog records the same remove-and-redeploy requirement with the bug reference.

## Report

Close with a summary covering:

- validator status before and after, by check slug;
- rocks and charms migrated, with their new bases;
- local lint, unit and license-header results;
- runtime checks on a real deployment: unit reaches `active`, and files the charm writes exist in the workload container with the expected owner and mode;
- renames applied outside the charm (Terraform, CI, bundles, docs);
- integrations converted to `CustomRelation`, and their `optional` flag;
- `paas-config.yaml` keys adopted and what they replaced;
- operator actions that remain: reapplying the `app-secret-key` secret, the session reset, the
  `--resource app-image=` refresh (for Flask and Django, removing and redeploying the charm
  because of LP#1991955), and any Redis-to-Valkey data migration.
