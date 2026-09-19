"""ADR-003: every dependency in pyproject.toml has a register row."""

import re
import tomllib
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

PYPROJECT = Path("pyproject.toml")
NAME = re.compile(r"^[A-Za-z0-9_.-]+")
REGISTER_ROW = re.compile(r"^\| (?P<cell>[^|]+)\|", re.M)
BACKTICKED = re.compile(r"`([^`]+)`")


def declared_dependencies(pyproject: dict[str, object]) -> set[str]:
    """Normalised names of every runtime and dev dependency."""
    project = pyproject.get("project", {})
    groups = pyproject.get("dependency-groups", {})
    specs: list[str] = list(project.get("dependencies", [])) if isinstance(project, dict) else []
    if isinstance(groups, dict):
        for group in groups.values():
            specs.extend(spec for spec in group if isinstance(spec, str))
    names = set()
    for spec in specs:
        match = NAME.match(spec)
        if match:
            names.add(match.group(0).lower().replace("_", "-"))
    return names


def registered(register_text: str) -> set[str]:
    """Names mentioned in the register's first column, split on commas and stripped of extras."""
    names = set()
    for match in REGISTER_ROW.finditer(register_text):
        for part in BACKTICKED.findall(match.group("cell")):
            cleaned = part.strip().split("[")[0].split(" ")[0].lower().replace("_", "-")
            if cleaned:
                names.add(cleaned)
    return names


def check(dependencies: set[str], register: set[str]) -> list[Violation]:
    """Report dependencies without a register row."""
    return [
        Violation(
            PYPROJECT.as_posix(), 1, f"{name} has no register row in {rules.REGISTER.as_posix()}"
        )
        for name in sorted(dependencies - register)
    ]


def run(root: Path) -> list[Violation]:
    """Read pyproject.toml and the register page."""
    pyproject = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))
    register_path = root / rules.REGISTER
    text = register_path.read_text(encoding="utf-8") if register_path.exists() else ""
    return check(declared_dependencies(pyproject), registered(text))
