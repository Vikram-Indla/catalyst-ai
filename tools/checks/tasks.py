"""RULE-002 §3: no fire-and-forget task; every created task is held."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

TASK_CALLS = ("asyncio.create_task", "create_task", "asyncio.ensure_future", "ensure_future")


def run(root: Path) -> list[Violation]:
    """Report a task created as a bare expression statement."""
    violations = []
    for path in walk(root, rules.SRC):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                name = ast.unparse(node.value.func)
                if name in TASK_CALLS:
                    violations.append(
                        Violation(relative(path, root), node.lineno, f"{name} result is not held")
                    )
    return violations
