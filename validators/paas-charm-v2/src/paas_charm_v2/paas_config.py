# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Schema validation for the charm-owned ``paas-config.yaml`` file.

The schema mirrors the ``paas-charm`` 2.0 reference documentation: top-level
``port``, ``metrics-port``, ``metrics-path``, ``framework_logging_format``,
``prometheus``, ``relations`` and ``config`` keys.
"""

import re
from collections.abc import Mapping
from typing import Any

TOP_LEVEL_KEYS = frozenset(
    {
        "port",
        "metrics-port",
        "metrics-path",
        "framework_logging_format",
        "prometheus",
        "config",
        "relations",
    }
)

# Structured framework logging is only implemented for the Gunicorn/Uvicorn frameworks.
STRUCTURED_LOGGING_FRAMEWORKS = frozenset({"flask", "django", "fastapi"})

_METRICS_PATH = re.compile(r"^/[A-Za-z0-9\-._~!$&'()*+,;=:@%/]*$")


def _check_port(key: str, value: Any) -> list[str]:
    """Return violations for a port field."""
    if not isinstance(value, int) or isinstance(value, bool):
        return [f"paas-config.yaml: {key} must be an integer"]
    if not 1 <= value <= 65535:
        return [f"paas-config.yaml: {key} must be between 1 and 65535"]
    return []


def _check_prometheus(section: Any) -> list[str]:
    """Return violations for the ``prometheus`` section."""
    if not isinstance(section, dict):
        return ["paas-config.yaml: prometheus must be a mapping"]
    unknown = set(section) - {"scrape_configs"}
    violations = [
        f"paas-config.yaml: unknown prometheus field: {name}" for name in sorted(unknown)
    ]
    jobs = section.get("scrape_configs")
    if jobs is None:
        return violations
    if not isinstance(jobs, list):
        return [*violations, "paas-config.yaml: prometheus.scrape_configs must be a list"]
    seen: set[str] = set()
    for index, job in enumerate(jobs):
        where = f"prometheus.scrape_configs[{index}]"
        if not isinstance(job, dict):
            violations.append(f"paas-config.yaml: {where} must be a mapping")
            continue
        job_name = job.get("job_name")
        if not isinstance(job_name, str) or not job_name:
            violations.append(f"paas-config.yaml: {where}.job_name is required")
        elif job_name in seen:
            violations.append(f"paas-config.yaml: duplicate scrape job_name: {job_name}")
        else:
            seen.add(job_name)
        static_configs = job.get("static_configs")
        if not isinstance(static_configs, list) or not static_configs:
            violations.append(f"paas-config.yaml: {where}.static_configs is required")
            continue
        for static_index, static in enumerate(static_configs):
            static_where = f"{where}.static_configs[{static_index}]"
            if not isinstance(static, dict):
                violations.append(f"paas-config.yaml: {static_where} must be a mapping")
                continue
            targets = static.get("targets")
            if not isinstance(targets, list) or not targets:
                violations.append(f"paas-config.yaml: {static_where}.targets is required")
    return violations


def _check_config(section: Any, declared_options: Mapping[str, str | None] | None) -> list[str]:
    """Return violations for the ``config.options`` environment variable mappings.

    ``declared_options`` maps each option declared in ``charmcraft.yaml`` to its type. When it
    is None, the option names and types are not checked.
    """
    if not isinstance(section, dict):
        return ["paas-config.yaml: config must be a mapping"]
    unknown = set(section) - {"options"}
    violations = [f"paas-config.yaml: unknown config field: {name}" for name in sorted(unknown)]
    options = section.get("options")
    if options is None:
        return violations
    if not isinstance(options, dict):
        return [*violations, "paas-config.yaml: config.options must be a mapping"]
    destinations: dict[str, str] = {}
    for name, mapping in options.items():
        where = f"config.options.{name}"
        if declared_options is not None and str(name) not in declared_options:
            violations.append(
                f"paas-config.yaml: {where} does not match a config option declared in "
                "charmcraft.yaml"
            )
        if not isinstance(mapping, dict):
            violations.append(f"paas-config.yaml: {where} must be a mapping")
            continue
        fields = set(mapping) & {"env-var", "secret-env-vars"}
        if len(fields) != 1 or set(mapping) - fields:
            violations.append(
                f"paas-config.yaml: {where} must use exactly one of env-var or secret-env-vars"
            )
            continue
        option_type = (declared_options or {}).get(str(name))
        if "env-var" in mapping and option_type == "secret":
            violations.append(
                f"paas-config.yaml: {where} is a secret option; map it with secret-env-vars"
            )
        elif "secret-env-vars" in mapping and option_type not in (None, "secret"):
            violations.append(
                f"paas-config.yaml: {where} is a {option_type} option; map it with env-var"
            )
        if "env-var" in mapping:
            targets = {str(name): mapping["env-var"]}
        else:
            if not isinstance(mapping["secret-env-vars"], dict):
                violations.append(f"paas-config.yaml: {where}.secret-env-vars must be a mapping")
                continue
            targets = {f"{name}.{key}": value for key, value in mapping["secret-env-vars"].items()}
        for source, destination in targets.items():
            if not isinstance(destination, str) or not destination or "=" in destination:
                violations.append(
                    f"paas-config.yaml: config.options.{source} maps to an invalid environment "
                    "variable name"
                )
                continue
            if destination in destinations:
                violations.append(
                    f"paas-config.yaml: duplicate environment variable destination "
                    f"{destination} ({destinations[destination]} and {source})"
                )
            else:
                destinations[destination] = source
    return violations


def _check_relations(section: Any, oauth_endpoints: set[str] | None) -> list[str]:
    """Validate the static OAuth settings supported since 2.0b3."""
    if not isinstance(section, dict):
        return ["paas-config.yaml: relations must be a mapping"]
    violations = []
    for endpoint, settings in section.items():
        where = f"paas-config.yaml: relations.{endpoint}"
        if oauth_endpoints is not None and endpoint not in oauth_endpoints:
            violations.append(f"{where} must name a requires endpoint with interface oauth")
        if not isinstance(settings, dict):
            violations.append(f"{where} must be a mapping")
            continue
        for key in settings.keys() - {"redirect-path", "scopes"}:
            violations.append(f"{where}: unknown field {key!r}")
        if "redirect-path" in settings:
            path = settings["redirect-path"]
            if not isinstance(path, str) or not path:
                violations.append(f"{where}.redirect-path must be a non-empty string")
        if "scopes" in settings:
            scopes = settings["scopes"]
            if (
                not isinstance(scopes, list)
                or "openid" not in scopes
                or any(not isinstance(s, str) or not s or re.search(r"\s", s) for s in scopes)
            ):
                violations.append(
                    f"{where}.scopes must list non-empty strings without whitespace, "
                    "including openid"
                )
    return violations


def check_paas_config(
    config: dict[str, Any],
    framework: str | None = None,
    declared_options: Mapping[str, str | None] | None = None,
    oauth_endpoints: set[str] | None = None,
) -> list[str]:
    """Return violations for a parsed ``paas-config.yaml`` document."""
    violations = [
        f"paas-config.yaml: unknown top-level field: {name}"
        for name in sorted(set(config) - TOP_LEVEL_KEYS)
    ]
    for key in ("port", "metrics-port"):
        if key in config:
            violations += _check_port(key, config[key])
    if "metrics-path" in config:
        path = config["metrics-path"]
        if not isinstance(path, str) or not _METRICS_PATH.match(path):
            violations.append("paas-config.yaml: metrics-path must be a slash-prefixed HTTP path")
    if "framework_logging_format" in config:
        value = config["framework_logging_format"]
        if value != "json":
            violations.append("paas-config.yaml: framework_logging_format must be json")
        elif framework is not None and framework not in STRUCTURED_LOGGING_FRAMEWORKS:
            violations.append(
                f"paas-config.yaml: framework_logging_format: json is not supported for "
                f"the {framework} framework"
            )
    if "prometheus" in config:
        violations += _check_prometheus(config["prometheus"])
    if "config" in config:
        violations += _check_config(config["config"], declared_options)
    if "relations" in config:
        violations += _check_relations(config["relations"], oauth_endpoints)
    return violations
