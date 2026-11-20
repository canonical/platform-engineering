# Migrating a hand-coded integration to a custom relation

`paas_charm.relations` is the public, stable extension API in `paas-charm` 2.0. Charm authors
never import or subclass `paas-charm` internals.

## The API

| Member | Role |
| --- | --- |
| `CustomRelation` | Base class for an author-owned relation. |
| `Context` | Read-only state injected before `setup()`: `app_name`, `framework_name`, `port`, `container_name`, and a merged `config` dict with Juju secret values resolved. Available as `self.context`. |
| `OnChange` | Callback the framework passes to `setup()`; call it to request reconcile/restart, optionally re-running migrations. |
| `RelationDataError`, `InvalidRelationDataError` | Re-exported exceptions signalling "not ready" and "data present but malformed". |

`self.charm` is an escape hatch for requirer libraries that need an `ops.CharmBase`, and for
live model state (`self.charm.model.get_relation(...)`, `self.charm.unit.is_leader()`).
Prefer `self.context` when no charm library forces otherwise.

## Method mapping

| Method | Env-var relation | Side-effect relation |
| --- | --- | --- |
| `setup(on_change)` (required) | Instantiate the requirer, wire its events to `on_change`. | Wire relation events; call the `require_*` helper. |
| `ensure_ready()` | Raise `RelationDataError` when not ready, `InvalidRelationDataError` when data is malformed. | Leave as the default no-op so it never blocks the workload. |
| `gen_environment()` | Read the databag, return `dict[str, str]`. Must never raise intentionally. | Leave as the default `{}`. |

Use the helper `self._framework_observe(bound_event, on_change, rerun_migrations=...)` to
observe events: it binds `on_change` as a method of an `ops.Object`, which Ops requires. Pass
`rerun_migrations=True` when the event should also re-run database migrations.

## Before: hand-coded in `src/charm.py`

```python
class FlaskCharm(paas_charm.flask.Charm):
    def __init__(self, *args):
        super().__init__(*args)
        self._temporal = TemporalHostInfoRequirer(self)
        self.framework.observe(
            self._temporal.on.temporal_host_info_changed, self._on_temporal_changed
        )

    def _on_temporal_changed(self, _event):
        relation = self.model.get_relation("temporal-host-info")
        if relation is None:
            self.unit.status = ops.BlockedStatus("missing temporal")
            return
        self._env["TEMPORAL_HOST"] = self._temporal.host
        self._env["TEMPORAL_PORT"] = str(self._temporal.port)
        self._restart()
```

## After: a `CustomRelation`

```python
import ops

from charms.temporal_k8s.v0.temporal_host_info import TemporalHostInfoRequirer

import paas_charm.flask
from paas_charm.relations import (
    CustomRelation,
    InvalidRelationDataError,
    OnChange,
    RelationDataError,
)


class TemporalRelation(CustomRelation):
    relation_name = "temporal-host-info"

    def setup(self, on_change: OnChange) -> None:
        self._requirer = TemporalHostInfoRequirer(self.charm)
        self._framework_observe(self._requirer.on.temporal_host_info_changed, on_change)
        self._framework_observe(self._requirer.on.temporal_host_info_unavailable, on_change)

    def ensure_ready(self) -> None:
        if self._requirer is None or self._requirer.relation is None:
            raise RelationDataError("Temporal relation not ready", relation=self.relation_name)
        self._connection_info()

    def gen_environment(self) -> dict[str, str]:
        connection_info = self._connection_info()
        if connection_info is None:
            return {}
        host, port = connection_info
        return {"TEMPORAL_HOST": host, "TEMPORAL_PORT": str(port)}

    def _connection_info(self) -> tuple[str, int] | None:
        if self._requirer is None or self._requirer.relation is None:
            return None
        host, port = self._requirer.host, self._requirer.port
        if not host or port is None:
            raise InvalidRelationDataError(
                "missing Temporal host or port", relation=self.relation_name
            )
        if not 1 <= port <= 65535:
            raise InvalidRelationDataError(
                "Temporal port must be between 1 and 65535", relation=self.relation_name
            )
        return host, port


class FlaskCharm(paas_charm.flask.Charm):
    custom_relations = [TemporalRelation]


if __name__ == "__main__":
    ops.main.main(FlaskCharm)
```

Register the class, not an instance. The framework instantiates it as `cls(charm)`, injects
`Context` and the required flag, and calls `setup(on_change=self._reconcile)`.

## Declaring the endpoint

```yaml
requires:
  temporal-host-info:
    interface: temporal-host-info
    optional: true
    limit: 1

charm-libs:
  - lib: temporal-k8s.temporal_host_info
    version: "0"
```

The endpoint must exist under `requires`: the framework validates this during initialization and
aborts otherwise. `optional` is the single source of truth for required versus optional, and
defaults to `false`.

## Behaviour

| Situation | Outcome |
| --- | --- |
| No relation, `optional: true` | No environment, no block. |
| No relation, `optional: false` | `BlockedStatus("missing integrations: <name>")`. |
| Related, `ensure_ready()` raises | `BlockedStatus("RelationDataError: <message>")`, optional or not. |
| Related and valid | Variables appear in the workload environment and the service restarts. |
| Relation removed | Variables removed, workload restarted. |

`gen_environment()` is called unconditionally, even when the relation is not ready, so it must
return rather than raise. Raising `RelationDataError` there blocks the charm; any other
exception fails the hook.

## Ordering caveat

`custom_relations` is processed inside `PaasCharm.__init__`, which runs **before** a subclass'
`__init__` body. A relation must be self-contained: it may use `self.context` and `self.charm`,
but not attributes the charm sets after `super().__init__()`. Push author state into the
relation instead of the charm constructor.

## Environment precedence

Lowest to highest: charm config and framework settings → built-in relations and Prometheus
metrics → custom relations in registration order → `config.options` mappings from
`paas-config.yaml`. A custom variable that collides with an existing one overwrites it and logs
a warning naming the relation and the variable.

Custom relations emit one definitive environment mapping, authored directly in
`gen_environment()`. There is no per-framework remapping: a 12-factor charm targets exactly one
framework, so emit the names that framework's workload expects.

## Missing libraries

The framework does not wrap `setup()` or `gen_environment()` in `try/except ImportError`. A
missing author-supplied charm library surfaces as an ordinary charm error. Guard or defer the
import if a softer failure mode is needed.
