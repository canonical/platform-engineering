"""Check the structure of skills and knowledge base entries in a repository.

Usage: ``uvx --from <this repo> pfe-check-structure [path]``
"""

import argparse
import re
import sys
from pathlib import Path

_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def parse_front_matter(path: Path) -> dict[str, str]:
    """Parse flat ``key: value`` front matter of a Markdown file.

    Args:
        path: Markdown file.

    Returns:
        The front matter keys and values, empty if there is none.
    """
    match = _FRONT_MATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            result[key.strip()] = value.strip().strip("\"'")
    return result


def check_skills(root: Path) -> list[str]:
    """Check that each skill has a valid SKILL.md."""
    errors = []
    skills = root / "skills"
    for skill_dir in sorted(p for p in skills.glob("*") if p.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{skill_dir}: missing SKILL.md")
            continue
        meta = parse_front_matter(skill_file)
        if meta.get("name") != skill_dir.name:
            errors.append(f"{skill_file}: front matter 'name' must be '{skill_dir.name}'")
        if not meta.get("description"):
            errors.append(f"{skill_file}: missing front matter 'description'")
    return errors


def check_kb(root: Path) -> list[str]:
    """Check that each KB entry has title and owner front matter."""
    errors = []
    for entry in sorted((root / "kb").rglob("*.md")):
        if entry.name == "README.md":
            continue
        meta = parse_front_matter(entry)
        errors.extend(
            f"{entry}: missing front matter '{key}'"
            for key in ("title", "owner")
            if not meta.get(key)
        )
    return errors


def main(argv: list[str] | None = None) -> int:
    """Run the validator.

    Args:
        argv: Command line arguments.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", default=".", type=Path)
    args = parser.parse_args(argv)
    errors = check_skills(args.path) + check_kb(args.path)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
