"""RULE-001 §2: a route is thin — few statements, no branch on content."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, python_files, relative

ROUTE_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
BRANCHES = (ast.If, ast.For, ast.While, ast.Try, ast.Match)


def _is_route(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute) and target.attr in ROUTE_METHODS:
            return True
    return False


def run(root: Path) -> list[Violation]:
    """Report routes over the statement budget or branching on anything."""
    violations = []
    for path in python_files(root):
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) or not _is_route(node):
                continue
            statements = [
                s
                for s in node.body
                if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)
            ]
            where = relative(path, root)
            if len(statements) > rules.ROUTE_STATEMENT_BUDGET:
                budget = rules.ROUTE_STATEMENT_BUDGET
                message = (
                    f"route {node.name} has {len(statements)} statements; the budget is {budget}"
                )
                violations.append(Violation(where, node.lineno, message))
            if any(isinstance(child, BRANCHES) for child in ast.walk(node) if child is not node):
                violations.append(Violation(where, node.lineno, f"route {node.name} branches"))
    return violations
