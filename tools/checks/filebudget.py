"""RULE-001 §2: a file holds at most 300 logical lines."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, logical_lines, python_files, relative


def run(root: Path) -> list[Violation]:
    """Report every Python file over the budget."""
    violations = []
    for path in python_files(root):
        count = logical_lines(path.read_text(encoding="utf-8"))
        if count > rules.FILE_BUDGET:
            message = f"file has {count} logical lines; the budget is {rules.FILE_BUDGET}"
            violations.append(Violation(relative(path, root), 1, message))
    return violations
