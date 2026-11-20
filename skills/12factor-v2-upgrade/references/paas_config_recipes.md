# `paas-config.yaml` recipes

`paas-config.yaml` is a charm-owned, **build-time** file that sits next to
`charmcraft.yaml`. It is not `juju config`: its values are packaged into the charm and can only
be changed by repacking. On Ubuntu 26.04 LTS the framework extension stages it automatically —
no `dump` part is needed.

`paas-charm` treats every key as optional, but this migration always sets `port`,
`metrics-port` and `metrics-path` explicitly (the framework defaults below when not overridden),
and the validator requires them. Other omitted keys use the framework default. Invalid content fails the hook at
runtime, so validate before packing.

## Schema

```yaml
port: 8080                        # application server port
metrics-port: 9102                # port the workload serves metrics on
metrics-path: /metrics            # slash-prefixed HTTP path
framework_logging_format: json    # Flask, Django, FastAPI only
prometheus:
  scrape_configs:
    - job_name: unique-name       # required, unique
      metrics_path: /metrics      # optional, default /metrics
      static_configs:             # required
        - targets: ["*:8081"]     # required
          labels:
            role: worker
config:
  options:
    log-level:
      env-var: LOG_LEVEL
    credentials:
      secret-env-vars:
        username: SERVICE_USERNAME
        password: SERVICE_PASSWORD
```

## Framework defaults

| Framework | Port | Metrics port | Metrics path | Port variable |
| --- | --- | --- | --- | --- |
| Flask | 8000 | 9102 | `/metrics` | configured in Gunicorn |
| Django | 8000 | 9102 | `/metrics` | configured in Gunicorn |
| FastAPI | 8000 | 8000 | `/metrics` | `UVICORN_PORT` |
| ExpressJS | 8080 | 9464 | `/metrics` | `PORT` |
| Go | 8080 | 8080 | `/metrics` | `PORT` |
| Spring Boot | 8080 | 8080 | `/actuator/prometheus` | `SERVER_PORT` |

Ports must be between 1 and 65535. `metrics-path` must be a slash-prefixed RFC 3986 HTTP path;
Charmcraft validates it at build time.

The resolved `metrics-port` and `metrics-path` are always passed to the workload and published
as the framework Prometheus scrape job. Flask and Django receive framework-prefixed
`METRICS_PORT`/`METRICS_PATH`; FastAPI, ExpressJS and Go receive them unprefixed; Spring Boot
receives native `management.*` properties. The workload must actually serve that endpoint.

For Flask and Django, `metrics-port` does not move the statsd exporter port.

## Replacing retired config options

`app-port`, `webserver-port`, `metrics-port` and `metrics-path` no longer exist as Juju config
options for FastAPI, Go, ExpressJS and Spring Boot. If the 1.x deployment set any of them, the
value moves into `paas-config.yaml`:

```yaml
# was: juju config myapp app-port=9000 metrics-path=/internal/metrics
port: 9000
metrics-path: /internal/metrics
```

Warn the user that the setting is now build-time and that operators who relied on `juju config`
lose that control.

## Extra Prometheus jobs

Jobs under `prometheus.scrape_configs` are appended to the framework job, not replacing it.
They only publish targets to Prometheus: they do not configure a listener or probe the endpoint.

```yaml
prometheus:
  scrape_configs:
    - job_name: worker-metrics
      metrics_path: /metrics
      static_configs:
        - targets: ["*:8081"]          # every unit
          labels:
            role: worker
    - job_name: scheduler-metrics
      static_configs:
        - targets: ["@scheduler:8082"] # unit 0 only
```

`*` expands to all units; `@scheduler` targets unit 0, which is where a Celery beat or similar
singleton runs. Use this to replace bespoke `prometheus_scrape` wiring in `src/charm.py`.

## Structured logging

```yaml
framework_logging_format: json
```

Supported for Flask (Gunicorn), Django (Gunicorn) and FastAPI (Uvicorn) only. Requesting it for
Go, ExpressJS or Spring Boot fails validation. Output follows OTEL semantic conventions.

## Environment variable mappings

`config.options` renames the environment variables generated from charm configuration options
and secrets. It does not declare options or set values.

Rules:

- Each entry uses exactly **one** of `env-var` (plain option) or `secret-env-vars` (option with
  `type: secret`).
- Source names must match options declared in `charmcraft.yaml` or `config.yaml` exactly.
  `foo-bar` and `foo_bar` are treated identically and are rejected as ambiguous.
- Framework options with environment output can be mapped (`app-secret-key`, `flask-debug`).
  Options that only configure files or arguments cannot (`webserver-workers`).
- Keys that only exist in `paas-config.yaml`, such as `port`, are not config options and cannot
  be mapping sources.
- Destinations are used verbatim: no prefixing, no case changes. They must be non-empty and
  contain no `=` or NUL. Duplicate destinations are rejected, even when a source is unset.
- Mappings **replace** the default name; they are not aliases. In Flask,
  `log-level: {env-var: LOG_LEVEL}` emits `LOG_LEVEL` instead of `FLASK_LOG_LEVEL`.
- Defaults are mapped too: a `log-level` default of `info` emits `LOG_LEVEL=info` with no
  operator action.
- An option with no value adds no variable and leaves an existing destination untouched. Empty
  strings, `false` and `0` count as values.

Use this during the upgrade to keep a workload's existing variable names rather than rewriting
the application. For the secret key:

```yaml
config:
  options:
    app-secret-key:
      secret-env-vars:
        value: SESSION_SECRET
```

`app-secret-key` requires exactly one secret content entry named `value`. If a secret validates
but lacks a mapped key, the charm skips the entry and logs a warning naming the option, key and
destination — never the value.

Without a mapping, a user-defined option cannot replace a framework field of the same name: a
`application-root` option does not override Flask's `flask-application-root` unless mapped
explicitly.

## Precedence

Lowest to highest:

1. Charm configuration and framework-generated settings
2. Built-in relations and Prometheus metrics
3. Custom relations, in registration order
4. Explicit `config.options` mappings whose source has a value

The charm logs a warning when a relation or mapping replaces an existing variable, naming the
variable but never its value.

## Validation failures to expect

Invalid YAML, unknown fields, missing required fields in nested sections, invalid values,
unknown source options, mapping fields that do not match an option's declared type, duplicate
destinations, and ambiguous `foo-bar`/`foo_bar` source names. Validation runs when the charm
initializes to handle a hook, so a bad file puts the unit in error and needs a repack and a
`juju refresh`.
