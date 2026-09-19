"""RULE-003 §1, §3: nothing untyped crosses a route, a pipeline surface or the port."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

BOUNDARY_FILES = ("routes.py", "pipeline.py", "port.py")
BOUNDARY_DIRS = (rules.SRC / "contract", rules.SRC / "capabilities", rules.SRC / "providers")
UNTYPED = frozenset({"Any", "dict", "object"})


def _typed_container(annotation: ast.expr, node: ast.Name) -> bool:
    if not (isinstance(annotation, ast.Subscript) and node is annotation.value):
        return False
    inner = ast.unparse(annotation.slice)
    return "Any" not in inner and "object" not in inner


def _untyped_annotation(annotation: ast.expr | None) -> str | None:
    if annotation is None:
        return "missing annotation"
    problems = []
    for node in ast.walk(annotation):
        if isinstance(node, ast.Name) and node.id in UNTYPED:
            if not _typed_container(annotation, node):
                problems.append(f"untyped {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr == "Any":
            problems.append("untyped Any")
    return problems[0] if problems else None


def _function_violations(
    path: Path, root: Path, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> list[Violation]:
    violations = []
    where = relative(path, root)
    arguments = [a for a in node.args.args + node.args.kwonlyargs if a.arg not in {"self", "cls"}]
    for argument in arguments:
        problem = _untyped_annotation(argument.annotation)
        if problem:
            violations.append(
                Violation(where, node.lineno, f"{node.name}({argument.arg}): {problem}")
            )
    problem = _untyped_annotation(node.returns)
    if problem and node.name != "__init__":
        violations.append(Violation(where, node.lineno, f"{node.name} returns: {problem}"))
    return violations


def run(root: Path) -> list[Violation]:
    """Report untyped signatures on the boundary files of contract, capabilities and providers."""
    violations = []
    for path in walk(root, *BOUNDARY_DIRS):
        if path.name not in BOUNDARY_FILES and path.parent.name != "contract":
            continue
        for node in ast.walk(parse(path)):
            if isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef
            ) and not node.name.startswith("_"):
                violations.extend(_function_violations(path, root, node))
    return violations
