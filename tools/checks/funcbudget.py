"""RULE-001 §2: a function or method spans at most 50 lines."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, python_files, relative

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def run(root: Path) -> list[Violation]:
    """Report every function longer than the budget."""
    violations = []
    for path in python_files(root):
        for node in ast.walk(parse(path)):
            if not isinstance(node, FunctionNode) or node.end_lineno is None:
                continue
            length = node.end_lineno - node.lineno + 1
            if length > rules.FUNCTION_BUDGET:
                message = f"{node.name} spans {length} lines; the budget is {rules.FUNCTION_BUDGET}"
                violations.append(Violation(relative(path, root), node.lineno, message))
    return violations
