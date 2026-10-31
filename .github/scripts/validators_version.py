#!/usr/bin/env python3
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Validator version gate and tagger.

``check BASE_REF``: fail if a validator's code changed versus BASE_REF without a version bump,
or if the version is already tagged. ``tag``: create missing ``<validator>/v<version>`` tags
(and print them, one per line).
"""

import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

VALIDATORS = Path("validators")
# Paths (relative to a validator folder) whose changes require a release.
RELEASE_PATHS = ("src", "pyproject.toml")


def git(*args: str, check: bool = True) -> str:
    """Run git and return stdout."""
    result = subprocess.run(["git", *args], capture_output=True, text=True, check=check)  # noqa: S603, S607
    return result.stdout.strip()


def validators() -> list[Path]:
    """Return the validator folders."""
    return sorted(p.parent for p in VALIDATORS.glob("*/pyproject.toml"))


def version_of(text: str) -> Version:
    """Parse the project version from pyproject.toml content."""
    return Version(tomllib.loads(text)["project"]["version"])


def tag_exists(tag: str) -> bool:
    """Return whether a tag exists locally."""
    return bool(git("tag", "--list", tag))


def check(base_ref: str) -> int:
    """Return 1 if any validator changed without a version bump."""
    errors = []
    for folder in validators():
        name = folder.name
        try:
            head = version_of((folder / "pyproject.toml").read_text())
        except (InvalidVersion, KeyError) as exc:
            errors.append(f"{name}: invalid or missing version ({exc})")
            continue
        paths = [str(folder / p) for p in RELEASE_PATHS]
        changed = git("diff", "--name-only", f"{base_ref}...HEAD", "--", *paths)
        base_toml = git("show", f"{base_ref}:{folder}/pyproject.toml", check=False)
        if not base_toml:  # new validator
            if tag_exists(f"{name}/v{head}"):
                errors.append(f"{name}: tag {name}/v{head} already exists")
            continue
        base = version_of(base_toml)
        if changed and head <= base:
            errors.append(
                f"{name}: code changed but version is {head} (base: {base}); "
                "bump [project].version and run `uv lock` in validators/"
            )
        if head != base and tag_exists(f"{name}/v{head}"):
            errors.append(f"{name}: tag {name}/v{head} already exists")
    for error in errors:
        print(f"::error::{error}")
    return 1 if errors else 0


def tag() -> int:
    """Create and push missing tags for the current versions."""
    for folder in validators():
        name = folder.name
        version = version_of((folder / "pyproject.toml").read_text())
        new_tag = f"{name}/v{version}"
        if tag_exists(new_tag):
            continue
        git("tag", "-a", new_tag, "-m", f"{name} {version}")
        git("push", "origin", new_tag)
        print(new_tag)
    return 0


def main(argv: list[str]) -> int:
    """Run the requested command."""
    if argv[:1] == ["check"] and len(argv) == 2:
        return check(argv[1])
    if argv == ["tag"]:
        return tag()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
