# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Compliance checks and CLI for the ``paas-charm`` 2.0 / Ubuntu 26.04 LTS contract.

The rules encoded here come from the ``paas-charm`` 2.0 release notes and the
"Upgrade to paas-charm 2.0" how-to guide.
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paas_charm_v2.paas_config import check_paas_config
from paas_charm_v2.project import (
    ProjectError,
    RENAMED_CONTAINER_FRAMEWORKS,
    CharmProject,
    Project,
    RockProject,
    discover,
    load_yaml,
)

TARGET_BASE = "ubuntu@26.04"

CHECK_SLUGS = (
    "charm-base",
    "rock-base",
    "uv-plugin",
    "paas-charm-pin",
    "workload-container",
    "paas-config",
    "custom-relations",
    "charm-contract",
    "charm-hooks",
    "repo-ci",
)

# Relations handled by paas-charm itself; anything else under `requires` is the
# charm author's own integration and belongs in a CustomRelation subclass.
BUILT_IN_ENDPOINTS = frozenset(
    {
        "ingress",
        "logging",
        "postgresql",
        "mysql",
        "mongodb",
        "valkey",
        "s3",
        "saml",
        "rabbitmq",
        "tracing",
        "smtp",
        "openfga",
        "oidc",
        "http-proxy",
    }
)

# Names removed or renamed by paas-charm 2.0.
RETIRED_CONFIG_OPTIONS = {
    "app-secret-key-id": "removed; app-secret-key is a single option of type secret",
    "flask-secret-key": "replaced by the secret-typed app-secret-key option",
    "django-secret-key": "replaced by the secret-typed app-secret-key option",
    "app-port": "replaced by the port field in paas-config.yaml",
    "webserver-port": "replaced by the port field in paas-config.yaml",
    "metrics-port": "replaced by the metrics-port field in paas-config.yaml",
    "metrics-path": "replaced by the metrics-path field in paas-config.yaml",
}


@dataclass(frozen=True)
class CheckResult:
    """Result of one category of compliance checks."""

    slug: str
    name: str
    violations: tuple[str, ...]
    skip_reason: str | None = None


@dataclass(frozen=True)
class ProjectReport:
    """Compliance report for one repository."""

    root: Path
    framework: str | None
    checks: tuple[CheckResult, ...]

    @property
    def violations(self) -> list[str]:
        """Return all violations across check categories."""
        return [violation for check in self.checks for violation in check.violations]


def _relative(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` when possible."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def find_uv_lock(charm: CharmProject, root: Path) -> Path | None:
    """Return the ``uv.lock`` used by the charm: in its directory or any parent up to ``root``."""
    directory = charm.directory.resolve()
    top = root.resolve()
    while True:
        candidate = directory / "uv.lock"
        if candidate.is_file():
            return candidate
        if directory == top or top not in directory.parents:
            return None
        directory = directory.parent


def check_charm_base(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for the charm base."""
    where = _relative(charm.directory / "charmcraft.yaml", root)
    if "bases" in charm.charmcraft:
        return [
            f"{where}: uses the legacy `bases` key; paas-charm 2.0 charms declare "
            f"`base: {TARGET_BASE}`"
        ]
    base = charm.charmcraft.get("base")
    if base != TARGET_BASE:
        return [f"{where}: base is {base!r}, expected {TARGET_BASE!r}"]
    return []


def check_rock_base(rock: RockProject, root: Path) -> list[str]:
    """Return violations for the rock base and build base."""
    where = _relative(rock.directory / "rockcraft.yaml", root)
    base = rock.rockcraft.get("base")
    build_base = rock.rockcraft.get("build-base")
    if base == "bare":
        if build_base != TARGET_BASE:
            return [f"{where}: bare base needs build-base: {TARGET_BASE}, found {build_base!r}"]
        return []
    if base != TARGET_BASE:
        return [
            f"{where}: base is {base!r}, expected {TARGET_BASE!r} "
            f"(or base: bare with build-base: {TARGET_BASE})"
        ]
    if build_base is not None and build_base != TARGET_BASE:
        return [f"{where}: build-base is {build_base!r}, expected {TARGET_BASE!r}"]
    return []


def check_uv_plugin(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for uv-based dependency management."""
    violations: list[str] = []
    where = _relative(charm.directory / "charmcraft.yaml", root)
    charm_part = (charm.charmcraft.get("parts") or {}).get("charm") or {}
    plugin = charm_part.get("plugin")
    if plugin is not None and plugin != "uv":
        violations.append(f"{where}: parts.charm uses the {plugin!r} plugin, expected 'uv'")
    if "charm-strict-dependencies" in charm_part:
        violations.append(
            f"{where}: parts.charm keeps charm-strict-dependencies, which the uv plugin "
            "does not need"
        )
    if plugin == "uv" and "astral-uv" not in (charm_part.get("build-snaps") or []):
        violations.append(f"{where}: parts.charm is missing the astral-uv build snap")
    if charm.pyproject is None:
        violations.append(
            f"{_relative(charm.directory, root)}: missing pyproject.toml; the uv plugin "
            "replaces requirements.txt"
        )
    if charm.has_requirements_txt:
        violations.append(
            f"{_relative(charm.directory / 'requirements.txt', root)}: delete it; "
            "dependencies are declared in pyproject.toml"
        )
    if find_uv_lock(charm, root) is None:
        violations.append(
            f"{_relative(charm.directory, root)}: missing uv.lock; generate it with "
            "`uv lock` and commit it (charmcraft pack fails without it)"
        )
    return violations


_CLAUSE = re.compile(r"^(==|>=|<=|!=|~=|>|<)?\s*([0-9]+(?:\.[0-9A-Za-z]+)*)(\.\*)?$")


def _version_tuple(text: str) -> tuple[int, ...]:
    """Return the leading numeric components of a version string."""
    parts: list[int] = []
    for component in text.split("."):
        match = re.match(r"^[0-9]+", component)
        if match is None:
            break
        parts.append(int(match.group()))
    return tuple(parts) or (0,)


def _pin_allows_only_v2(specifier: str) -> bool:
    """True if the specifier admits a 2.x release and excludes 3.0 and later.

    Accepts exact and wildcard pins such as ``==2.0`` or ``==2.0.*`` and bounded
    ranges such as ``>=2,<3`` or ``>=2.0.dev1,<3``.
    """
    has_lower_bound = False
    has_upper_bound = False
    for clause in specifier.split(","):
        match = _CLAUSE.match(clause.strip())
        if match is None:
            return False
        operator, version, wildcard = match.groups()
        value = _version_tuple(version)
        if operator in ("==", "~=", None) or wildcard:
            if value[0] != 2:
                return False
            has_lower_bound = has_upper_bound = True
        elif operator in (">=", ">"):
            if value[0] != 2:
                return False
            has_lower_bound = True
        elif operator in ("<", "<="):
            limit = (3, 0) if operator == "<" else (2, float("inf"))
            if value > limit:
                return False
            has_upper_bound = True
    return has_lower_bound and has_upper_bound


def check_paas_charm_pin(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for the paas-charm dependency pin in pyproject.toml."""
    if charm.pyproject is None:
        if charm.has_requirements_txt:
            path = charm.directory / "requirements.txt"
            text = path.read_text(encoding="utf-8", errors="replace")
            if re.search(r"^\s*paas[-_]charm", text, re.MULTILINE):
                return [
                    f"{_relative(path, root)}: paas-charm is pinned in requirements.txt; "
                    'declare "paas-charm>=2.0.dev1,<3" in pyproject.toml instead'
                ]
        return []
    where = _relative(charm.directory / "pyproject.toml", root)
    dependencies = (charm.pyproject.get("project") or {}).get("dependencies") or []
    violations: list[str] = []
    found: str | None = None
    for dependency in dependencies:
        text = str(dependency)
        name_match = re.match(r"^[A-Za-z0-9._-]+", text)
        if name_match is None or name_match.group().lower().replace("_", "-") != "paas-charm":
            continue
        found = text
        specifier = re.sub(r"^\[[^\]]*\]", "", text[name_match.end() :].strip()).strip()
        if not specifier:
            violations.append(
                f"{where}: paas-charm is unpinned; require 2.x "
                '(for example "paas-charm>=2.0.dev1,<3")'
            )
        elif not _pin_allows_only_v2(specifier):
            violations.append(
                f"{where}: paas-charm pin {specifier!r} does not resolve to 2.x only "
                '(use "==2.0.*" or ">=2.0.dev1,<3")'
            )
    if found is None:
        violations.append(f"{where}: project.dependencies does not declare paas-charm")
    requires_python = (charm.pyproject.get("project") or {}).get("requires-python")
    if requires_python is not None and not _requires_python_312(str(requires_python)):
        violations.append(
            f"{where}: requires-python is {requires_python!r}; paas-charm 2.0 needs >=3.12"
        )
    return violations


def _requires_python_312(specifier: str) -> bool:
    """True if the requires-python specifier admits only Python 3.12 or greater."""
    for clause in specifier.split(","):
        match = _CLAUSE.match(clause.strip())
        if match is None:
            continue
        operator, version, _ = match.groups()
        if operator in (">=", ">", "==", "~=") and _version_tuple(version) >= (3, 12):
            return True
    return False


def check_workload_container(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for the workload container and OCI resource names."""
    where = _relative(charm.directory / "charmcraft.yaml", root)
    violations: list[str] = []
    containers = charm.charmcraft.get("containers") or {}
    resources = charm.charmcraft.get("resources") or {}
    if containers and "app" not in containers:
        violations.append(
            f"{where}: workload container is {sorted(containers)}, expected 'app' "
            "(flask-app and django-app were renamed in paas-charm 2.0)"
        )
    for name, body in containers.items():
        resource = (body or {}).get("resource")
        if name == "app" and resource not in (None, "app-image"):
            violations.append(
                f"{where}: containers.app.resource is {resource!r}, expected 'app-image'"
            )
    for name in resources:
        if name.endswith("-app-image"):
            violations.append(f"{where}: resources.{name} should be renamed to 'app-image'")
    return violations


def check_rock_workload(rock: RockProject, root: Path) -> list[str]:
    """Return violations for framework-prefixed paths and part names in a rock."""
    where = _relative(rock.directory / "rockcraft.yaml", root)
    framework = rock.framework
    violations: list[str] = []
    parts = rock.rockcraft.get("parts") or {}
    for name in parts:
        if "/" in str(name):
            violations.append(
                f"{where}: part {name!r} uses the '/' separator; Ubuntu 26.04 LTS "
                f"extension part names use '.' (for example {str(name).replace('/', '.', 1)})"
            )
    install_app = parts.get("install-app") or {}
    for entry in install_app.get("prime") or []:
        if not str(entry).startswith("app"):
            violations.append(
                f"{where}: parts.install-app.prime entry {entry!r} must start with 'app' "
                "on Ubuntu 26.04 LTS"
            )
    if framework in RENAMED_CONTAINER_FRAMEWORKS and framework in ("flask", "django"):
        override = (parts.get(f"{framework}-framework.dependencies") or {}).get("override-build")
        if override and ".gunicorn-constraints.txt" not in str(override):
            violations.append(
                f"{where}: parts.{framework}-framework.dependencies overrides override-build, "
                "which replaces the extension's own and so never writes "
                ".gunicorn-constraints.txt; add `printf '%s\\n' 'gunicorn~=26.0' > "
                ".gunicorn-constraints.txt` before `craftctl default`"
            )
    if framework in RENAMED_CONTAINER_FRAMEWORKS:
        text = (rock.directory / "rockcraft.yaml").read_text(encoding="utf-8")
        for legacy in (f"/{framework}/app", f"/{framework}/state", "/app/state"):
            if legacy in text:
                violations.append(
                    f"{where}: references {legacy!r}; the application root is /app and charm "
                    "state lives in /tmp/paas-charm"
                )
    return violations


def check_custom_relations(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for hand-coded relation handling in the charm source."""
    violations: list[str] = []
    requires = charm.charmcraft.get("requires") or {}
    custom_endpoints = {name for name in requires if name not in BUILT_IN_ENDPOINTS}
    registered: set[str] = set()
    hand_coded: list[str] = []
    for source in charm.charm_sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        where = _relative(source, root)
        registered |= set(re.findall(r"relation_name\s*=\s*[\"']([^\"']+)[\"']", text))
        if "custom_relations" not in text:
            for match in re.finditer(
                r"\.observe\(\s*[^)]*relation_(created|joined|changed|departed|broken)", text
            ):
                line_number = text.count("\n", 0, match.start()) + 1
                hand_coded.append(
                    f"{where}:{line_number}: relation event observed directly; move this "
                    "integration into a paas_charm.relations.CustomRelation subclass"
                )
        if "paas_app_charmer" in text:
            violations.append(
                f"{where}: the paas_app_charmer import path was removed; import paas_charm"
            )
    violations += hand_coded
    for endpoint in sorted(custom_endpoints - registered):
        violations.append(
            f"{_relative(charm.directory / 'charmcraft.yaml', root)}: requires.{endpoint} is not "
            "a built-in relation and no CustomRelation declares it "
            f'(relation_name = "{endpoint}")'
        )
    for endpoint in sorted(registered - set(requires)):
        violations.append(
            f"{_relative(charm.directory / 'charmcraft.yaml', root)}: CustomRelation "
            f"{endpoint!r} is not declared under requires; the charm aborts at startup"
        )
    if "redis" in requires:
        violations.append(
            f"{_relative(charm.directory / 'charmcraft.yaml', root)}: the redis relation is "
            "replaced by valkey (REDIS_DB_* becomes VALKEY_DB_*)"
        )
    return violations


def check_charm_contract(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for the generated paas-charm 2.0 charm contract."""
    where = _relative(charm.directory / "charmcraft.yaml", root)
    violations: list[str] = []
    peers = charm.charmcraft.get("peers") or {}
    if "secret-storage" in peers:
        violations.append(
            f"{where}: the secret-storage peer relation is renamed to peers (interface: peers)"
        )
    elif peers and "peers" not in peers:
        violations.append(f"{where}: missing the 'peers' peer relation")
    options: dict[str, Any] = (charm.charmcraft.get("config") or {}).get("options") or {}
    for option, reason in RETIRED_CONFIG_OPTIONS.items():
        if option in options:
            violations.append(f"{where}: config option {option!r}: {reason}")
    secret_key = options.get("app-secret-key")
    if isinstance(secret_key, dict) and secret_key.get("type") != "secret":
        violations.append(f"{where}: config option 'app-secret-key' must be type: secret")
    for library in charm.charmcraft.get("charm-libs") or []:
        lib = str((library or {}).get("lib", ""))
        version = str((library or {}).get("version", ""))
        if lib == "loki-k8s.loki_push_api" and version == "0":
            violations.append(f"{where}: loki_push_api v0 is removed; fetch version 1")
        if lib.startswith("hydra."):
            violations.append(
                f"{where}: charms.hydra.v0.oauth is replaced by the charmlibs-interfaces-oauth "
                "Python dependency"
            )
    return violations


REMOVED_HOOKS = ("_on_config_changed", "_on_pebble_ready")

# Files that commonly install the charm's requirements or exclude files from checks.
CI_CONFIG_FILES = ("tox.ini", "pyproject.toml", "Makefile", "noxfile.py", "justfile")


def check_charm_hooks(charm: CharmProject, root: Path) -> list[str]:
    """Return violations for overrides of base-class hooks removed in paas-charm 2.0."""
    violations: list[str] = []
    for source in charm.charm_sources:
        text = source.read_text(encoding="utf-8", errors="replace")
        where = _relative(source, root)
        for hook in REMOVED_HOOKS:
            for match in re.finditer(rf"super\(\)\.{hook}\b", text):
                line_number = text.count("\n", 0, match.start()) + 1
                violations.append(
                    f"{where}:{line_number}: paas-charm 2.0 has no {hook}; the call fails "
                    "pylint (no-member) and the override never runs. Override _reconcile "
                    "(rerun_migrations: bool = False) and call super()._reconcile(...) instead"
                )
            if re.search(rf"def {hook}\b", text) and not re.search(
                rf"observe\([^)]*self\.{hook}\b", text
            ):
                violations.append(
                    f"{where}: {hook} is defined but never observed; paas-charm 2.0 no longer "
                    "calls it. Override _reconcile instead"
                )
    return violations


def _glob_regex(pattern: str) -> re.Pattern[str]:
    """Translate a license-config glob into a regular expression."""
    regex = ""
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            regex += "(?:.*/)?"
            index += 3
        elif pattern.startswith("**", index):
            regex += ".*"
            index += 2
        elif pattern[index] == "*":
            regex += "[^/]*"
            index += 1
        elif pattern[index] == "?":
            regex += "[^/]"
            index += 1
        else:
            regex += re.escape(pattern[index])
            index += 1
    return re.compile(regex)


def _licenserc_ignored_patterns(root: Path) -> list[str] | None:
    """Return the header ``paths-ignore`` patterns, or None when there is no license config."""
    for name in (".licenserc.yaml", ".licenserc.yml"):
        path = root / name
        if not path.is_file():
            continue
        try:
            config = load_yaml(path)
        except ProjectError:
            return []
        header = config.get("header") or {}
        sections = header if isinstance(header, list) else [header]
        patterns: list[str] = []
        for section in sections:
            if isinstance(section, dict):
                patterns += [str(item) for item in section.get("paths-ignore") or []]
        return patterns
    return None


def _is_ignored(relative: str, patterns: list[str]) -> bool:
    """Return whether ``relative`` is covered by any ignore pattern."""
    for pattern in patterns:
        pattern = pattern.strip().removeprefix("./")
        if not pattern:
            continue
        candidates = [pattern, pattern.rstrip("/") + "/**"]
        if "/" not in pattern:
            candidates += [f"**/{pattern}", f"**/{pattern}/**"]
        if any(_glob_regex(candidate).fullmatch(relative) for candidate in candidates):
            return True
    return False


def check_repo_ci(project: Project) -> list[str]:
    """Return violations in repository CI configuration affected by the migration."""
    root = project.root
    violations: list[str] = []
    ignored = _licenserc_ignored_patterns(root)
    reported: set[str] = set()
    for charm in project.charms:
        lock_path = find_uv_lock(charm, root)
        if lock_path is None:
            continue
        lock = _relative(lock_path, root)
        if ignored is not None and lock not in reported and not _is_ignored(lock, ignored):
            reported.add(lock)
            violations.append(
                f".licenserc.yaml: add {lock!r} to header.paths-ignore; the license header "
                "check fails on the generated uv.lock"
            )
        if charm.has_requirements_txt:
            continue
        requirements = _relative(charm.directory / "requirements.txt", root)
        for name in CI_CONFIG_FILES:
            path = root / name
            if path.is_file() and requirements in path.read_text(
                encoding="utf-8", errors="replace"
            ):
                violations.append(
                    f"{name}: references the removed {requirements}; install paas-charm "
                    "(for example 'paas-charm>=2.0.dev1,<3') or the charm dependency group "
                    "instead"
                )
    return violations


def build_report(project: Project) -> ProjectReport:
    """Run every check against a discovered project."""
    root = project.root
    framework = project.framework
    results: list[CheckResult] = []

    def add(slug: str, name: str, violations: list[str], skip: str | None = None) -> None:
        results.append(CheckResult(slug, name, tuple(violations), skip))

    parse_errors = [
        error for item in (*project.charms, *project.rocks) for error in item.parse_errors
    ]

    if not project.charms:
        add("charm-base", "Charm base", [], "no charmcraft.yaml found")
        add("uv-plugin", "uv plugin", [], "no charmcraft.yaml found")
        add("paas-charm-pin", "paas-charm 2.x pin", [], "no charmcraft.yaml found")
        add("workload-container", "Workload container", [], "no charmcraft.yaml found")
        add("paas-config", "paas-config.yaml", [], "no charmcraft.yaml found")
        add("custom-relations", "Custom relations", [], "no charmcraft.yaml found")
        add("charm-contract", "Charm contract", [], "no charmcraft.yaml found")
        add("charm-hooks", "Charm hooks", [], "no charmcraft.yaml found")
        add("repo-ci", "Repository CI", [], "no charmcraft.yaml found")
    else:
        add(
            "charm-hooks",
            "Charm hooks",
            [v for c in project.charms for v in check_charm_hooks(c, root)],
        )
        add("repo-ci", "Repository CI", check_repo_ci(project))
        add(
            "charm-base",
            "Charm base",
            [v for c in project.charms for v in check_charm_base(c, root)],
        )
        add(
            "uv-plugin",
            "uv plugin",
            [v for c in project.charms for v in check_uv_plugin(c, root)],
        )
        add(
            "paas-charm-pin",
            "paas-charm 2.x pin",
            [v for c in project.charms for v in check_paas_charm_pin(c, root)],
        )
        add(
            "workload-container",
            "Workload container",
            [v for c in project.charms for v in check_workload_container(c, root)],
        )
        add(
            "custom-relations",
            "Custom relations",
            [v for c in project.charms for v in check_custom_relations(c, root)],
        )
        add(
            "charm-contract",
            "Charm contract",
            [v for c in project.charms for v in check_charm_contract(c, root)],
        )
        paas_config_violations: list[str] = []
        missing = [c for c in project.charms if not c.has_paas_config_file]
        for charm in project.charms:
            if charm.paas_config is None:
                continue
            options = (charm.charmcraft.get("config") or {}).get("options") or {}
            prefix = _relative(charm.directory, root)
            paas_config_violations += [
                f"{prefix}/{violation}" if prefix not in ("", ".") else violation
                for violation in check_paas_config(
                    charm.paas_config, charm.framework or framework, frozenset(map(str, options))
                )
            ]
        skip = (
            "no paas-config.yaml found; add one to configure port, metrics and "
            "environment variable names"
            if len(missing) == len(project.charms)
            else None
        )
        add("paas-config", "paas-config.yaml", paas_config_violations, skip)

    if not project.rocks:
        add("rock-base", "Rock base", [], "no rockcraft.yaml found")
    else:
        rock_violations = [v for r in project.rocks for v in check_rock_base(r, root)]
        rock_violations += [v for r in project.rocks for v in check_rock_workload(r, root)]
        add("rock-base", "Rock base", rock_violations)

    if parse_errors:
        results.insert(0, CheckResult("parse", "Project files", tuple(parse_errors)))
    return ProjectReport(root=root, framework=framework, checks=tuple(results))


def format_report(report: ProjectReport, verbose: bool = False) -> str:
    """Render a report as human-readable text."""
    lines = [f"{report.root}", f"  framework: {report.framework or 'unknown'}"]
    for check in report.checks:
        if check.skip_reason and not check.violations:
            if verbose:
                lines.append(f"  - {check.name}: skipped ({check.skip_reason})")
            continue
        if not check.violations:
            if verbose:
                lines.append(f"  ✓ {check.name}")
            continue
        lines.append(f"  ✗ {check.name} [{check.slug}]")
        lines.extend(f"      {violation}" for violation in check.violations)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the validator CLI."""
    parser = argparse.ArgumentParser(
        description="Check a repository against the paas-charm 2.0 contract."
    )
    parser.add_argument("paths", nargs="*", type=Path, help="repository or project directories")
    parser.add_argument("--verbose", action="store_true", help="show passing and skipped checks")
    parser.add_argument("--check", action="append", help="only run the named check (repeatable)")
    parser.add_argument("--list-checks", action="store_true", help="list check slugs and exit")
    args = parser.parse_args(argv)

    if args.list_checks:
        print("\n".join(CHECK_SLUGS))
        return 0
    if not args.paths:
        parser.print_usage(sys.stderr)
        print("error: no directories given", file=sys.stderr)
        return 2
    if args.check:
        unknown = sorted(set(args.check) - set(CHECK_SLUGS))
        if unknown:
            print(f"error: unknown check(s): {', '.join(unknown)}", file=sys.stderr)
            return 2

    failed = False
    for path in args.paths:
        report = build_report(discover(path.resolve()))
        if args.check:
            report = ProjectReport(
                root=report.root,
                framework=report.framework,
                checks=tuple(c for c in report.checks if c.slug in args.check),
            )
        print(format_report(report, verbose=args.verbose))
        failed = failed or bool(report.violations)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
