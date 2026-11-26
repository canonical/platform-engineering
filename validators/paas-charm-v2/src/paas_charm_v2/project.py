# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Project discovery and file loading for 12-factor charm and rock projects."""

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

FRAMEWORKS = ("django", "expressjs", "fastapi", "flask", "go", "spring-boot")

# Frameworks whose workload container and OCI resource were renamed in paas-charm 2.0.
RENAMED_CONTAINER_FRAMEWORKS = ("flask", "django")

SKIPPED_DIRECTORIES = {
    ".git",
    ".tox",
    ".venv",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    "parts",
    "stage",
    "prime",
}


class ProjectError(Exception):
    """A project file exists but cannot be parsed."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file as a mapping.

    Raises:
        ProjectError: the file is not valid YAML or does not contain a mapping.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProjectError(f"{path.name}: invalid YAML: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ProjectError(f"{path.name}: expected a mapping at the top level")
    return data


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file as a mapping.

    Raises:
        ProjectError: the file is not valid TOML.
    """
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ProjectError(f"{path.name}: invalid TOML: {exc}") from exc


@dataclass(frozen=True)
class CharmProject:
    """A charm project directory containing ``charmcraft.yaml``."""

    directory: Path
    charmcraft: dict[str, Any]
    pyproject: dict[str, Any] | None
    paas_config: dict[str, Any] | None
    has_paas_config_file: bool
    has_uv_lock: bool
    has_requirements_txt: bool
    charm_sources: tuple[Path, ...]
    parse_errors: tuple[str, ...] = ()

    @property
    def oauth_endpoints(self) -> set[str]:
        """Return endpoint names handled by the built-in OAuth requirer."""
        return {
            name
            for name, body in (self.charmcraft.get("requires") or {}).items()
            if isinstance(body, dict) and body.get("interface") == "oauth"
        }

    @property
    def framework(self) -> str | None:
        """Return the 12-factor framework of the charm, if it can be determined."""
        for extension in self.charmcraft.get("extensions") or []:
            name = str(extension).removesuffix("-framework")
            if name in FRAMEWORKS:
                return name
        options = (self.charmcraft.get("config") or {}).get("options") or {}
        for framework in FRAMEWORKS:
            if any(str(option).startswith(f"{framework}-") for option in options):
                return framework
        return None


@dataclass(frozen=True)
class RockProject:
    """A rock project directory containing ``rockcraft.yaml``."""

    directory: Path
    rockcraft: dict[str, Any]
    parse_errors: tuple[str, ...] = ()

    @property
    def framework(self) -> str | None:
        """Return the 12-factor framework of the rock, if it can be determined."""
        for extension in self.rockcraft.get("extensions") or []:
            name = str(extension).removesuffix("-framework")
            if name in FRAMEWORKS:
                return name
        return None


@dataclass
class Project:
    """A repository containing zero or more charm and rock projects."""

    root: Path
    charms: list[CharmProject] = field(default_factory=list)
    rocks: list[RockProject] = field(default_factory=list)

    @property
    def framework(self) -> str | None:
        """Return the framework of the project, preferring the charm."""
        for candidate in (*self.charms, *self.rocks):
            if candidate.framework:
                return candidate.framework
        return None


def _walk(root: Path) -> list[Path]:
    """Return the directories under ``root``, skipping build and VCS directories."""
    directories: list[Path] = []
    for current, dirnames, _ in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIPPED_DIRECTORIES)
        directories.append(Path(current))
    return directories


def _load_charm(directory: Path) -> CharmProject:
    """Build a :class:`CharmProject` from a directory containing ``charmcraft.yaml``."""
    errors: list[str] = []

    def guarded(loader, path: Path):  # type: ignore[no-untyped-def]
        try:
            return loader(path)
        except ProjectError as exc:
            errors.append(str(exc))
            return None

    charmcraft = guarded(load_yaml, directory / "charmcraft.yaml") or {}
    pyproject_path = directory / "pyproject.toml"
    pyproject = guarded(load_toml, pyproject_path) if pyproject_path.exists() else None
    paas_config_path = directory / "paas-config.yaml"
    paas_config = guarded(load_yaml, paas_config_path) if paas_config_path.exists() else None
    sources = tuple(sorted(p for p in (directory / "src").rglob("*.py") if p.is_file()))
    return CharmProject(
        directory=directory,
        charmcraft=charmcraft,
        pyproject=pyproject,
        paas_config=paas_config,
        has_paas_config_file=paas_config_path.exists(),
        has_uv_lock=(directory / "uv.lock").exists(),
        has_requirements_txt=(directory / "requirements.txt").exists(),
        charm_sources=sources,
        parse_errors=tuple(errors),
    )


def _load_rock(directory: Path) -> RockProject:
    """Build a :class:`RockProject` from a directory containing ``rockcraft.yaml``."""
    try:
        rockcraft = load_yaml(directory / "rockcraft.yaml")
    except ProjectError as exc:
        return RockProject(directory=directory, rockcraft={}, parse_errors=(str(exc),))
    return RockProject(directory=directory, rockcraft=rockcraft)


def discover(root: Path) -> Project:
    """Discover the charm and rock projects under ``root``."""
    project = Project(root=root)
    for directory in _walk(root):
        if (directory / "charmcraft.yaml").is_file():
            project.charms.append(_load_charm(directory))
        if (directory / "rockcraft.yaml").is_file():
            project.rocks.append(_load_rock(directory))
    return project
