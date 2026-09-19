"""RULE-005 §6, RULE-007 §1: the claimed blast radius is never lower than the derived one."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation
from tools.checks.gitinfo import changed_since_main

CLAIM = re.compile(r"^Blast radius:\s*(?P<radius>[A-Z-]+)", re.MULTILINE)


def derive(changed: list[str]) -> str:
    """Return the blast radius the changed paths imply."""
    radius = "LOCAL"
    for path in changed:
        if path.startswith(rules.SYSTEM_PATHS):
            return "SYSTEM"
        if path.startswith(rules.PLATFORM_PATHS):
            radius = "PLATFORM"
        elif path.startswith(rules.CONTRACT_PATHS) and radius not in {"PLATFORM"}:
            radius = "CONTRACT"
        elif path.startswith(rules.CAPABILITY_PATHS) and radius == "LOCAL":
            radius = "CAPABILITY"
    return radius


def check(changed: list[str], records: dict[str, str]) -> list[Violation]:
    """Report a record whose claimed radius is below the derived one."""
    derived = derive(changed)
    violations = []
    for path, text in records.items():
        match = CLAIM.search(text)
        if match is None:
            continue
        claimed = match.group("radius")
        if claimed in rules.RADII and rules.RADII.index(claimed) < rules.RADII.index(derived):
            message = f"claims {claimed} but the changed paths derive {derived}"
            violations.append(Violation(path, 1, message))
    return violations


def run(root: Path) -> list[Violation]:
    """Read the branch's changed files and its changed session records."""
    changed = changed_since_main(root)
    prefix = rules.SESSIONS.as_posix() + "/"
    records = {
        path: (root / path).read_text(encoding="utf-8")
        for path in changed
        if path.startswith(prefix) and (root / path).exists()
    }
    return check(changed, records)
