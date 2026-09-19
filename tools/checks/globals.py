"""RULE-001 §5: no module-level mutable container; constants are tuples, frozensets, mappings."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

EXPORTS = "__all__"
MUTABLE_CALLS = frozenset({"list", "dict", "set", "defaultdict", "deque"})
MUTABLE_LITERALS = (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.DictComp, ast.SetComp)


def _is_mutable(value: ast.expr) -> bool:
    if isinstance(value, MUTABLE_LITERALS):
        return True
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in MUTABLE_CALLS
    )


def run(root: Path) -> list[Violation]:
    """Report every module-level assignment of a mutable container in the source tree."""
    violations = []
    for path in walk(root, rules.SRC):
        for node in parse(path).body:
            targets: list[ast.expr] = []
            value: ast.expr | None = None
            if isinstance(node, ast.Assign):
                targets, value = node.targets, node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets, value = [node.target], node.value
            names_bound = {ast.unparse(target) for target in targets}
            if value is not None and _is_mutable(value) and names_bound != {EXPORTS}:
                names = ", ".join(ast.unparse(target) for target in targets)
                message = f"module-level mutable container {names}; use a tuple or a frozenset"
                violations.append(Violation(relative(path, root), node.lineno, message))
    return violations
