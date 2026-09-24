"""RULE-005 §6, RULE-007 §1: the claimed blast radius is never lower than the derived one.

The derived radius is the branch's: every file that differs from `main`. A branch may carry several
records, one per proposed commit, each claiming its own change's radius; the branch is judged by
the highest of those claims, since the branch lands as one push and is reviewed at that class. A
record keeps its own true radius, and a branch whose every claim is below the derived one is red.
A changed record that claims no radius is red too, or one claim could stand for a silent rest; the
per-record truth is judged at each commit, by `commitclass`.
"""

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


def claims(records: dict[str, str]) -> dict[str, str]:
    """Return each record's claimed radius, for the records that claim a known one."""
    found = {path: CLAIM.search(text) for path, text in records.items()}
    return {
        path: match.group("radius")
        for path, match in found.items()
        if match is not None and match.group("radius") in rules.RADII
    }


def check(changed: list[str], records: dict[str, str]) -> list[Violation]:
    """Report a branch whose highest claimed radius is below the one its changed paths derive."""
    derived = derive(changed)
    claimed = claims(records)
    unclaimed = [
        Violation(path, 1, "a changed record claims no blast radius")
        for path in sorted(set(records) - set(claimed))
    ]
    if not claimed:
        return unclaimed
    highest = max(claimed.values(), key=rules.RADII.index)
    if rules.RADII.index(highest) >= rules.RADII.index(derived):
        return unclaimed
    message = f"the highest claim is {highest} but the changed paths derive {derived}"
    return unclaimed + [Violation(path, 1, message) for path in sorted(claimed)]


def run(root: Path) -> list[Violation]:
    """Read the branch's changed files and its changed session records."""
    changed = changed_since_main(root)
    prefix = rules.SESSIONS.as_posix() + "/"
    records = {
        path: (root / path).read_text(encoding="utf-8")
        for path in changed
        if path.startswith(prefix)
        and path.endswith(".md")
        and "_TEMPLATE" not in path
        and (root / path).exists()
    }
    return check(changed, records)
