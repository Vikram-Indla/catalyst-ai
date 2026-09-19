"""RULE-005 §1: the workflow holds only checkout, setup, make tools, make hooks, make verify."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<value>\S+)", re.M)
RUN = re.compile(r"^\s*-?\s*run:\s*(?P<value>.+)$", re.M)


def check(workflow: str, where: str) -> list[Violation]:
    """Report any step outside the allowed set and a missing `make verify`."""
    violations = []
    for match in USES.finditer(workflow):
        if match.group("value") not in rules.CI_ALLOWED_USES:
            violations.append(
                Violation(
                    where, 1, f"workflow uses {match.group('value')}, which the gate does not"
                )
            )
    runs = [m.group("value").strip() for m in RUN.finditer(workflow)]
    for command in runs:
        if command not in rules.CI_ALLOWED_RUNS:
            violations.append(
                Violation(where, 1, f"workflow runs {command!r}, which the gate does not")
            )
    if "make verify" not in runs:
        violations.append(Violation(where, 1, "workflow does not run `make verify`"))
    return violations


def run(root: Path) -> list[Violation]:
    """Read the committed workflow."""
    path = root / rules.WORKFLOW
    if not path.exists():
        return [Violation(rules.WORKFLOW.as_posix(), 1, "no workflow file")]
    return check(path.read_text(encoding="utf-8"), rules.WORKFLOW.as_posix())
