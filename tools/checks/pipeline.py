"""ARCH-003 §2: the stages run in order and the port is called only inside `call`."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

CAPABILITIES = rules.SRC / "capabilities"
RUN_FUNCTION = "run"
CALL_STAGE = "call"
STAGES_CLASS = "Stages"


def _called_names(node: ast.AST) -> list[str]:
    calls = sorted(
        (c for c in ast.walk(node) if isinstance(c, ast.Call)),
        key=lambda c: (c.lineno, c.col_offset),
    )
    names = []
    for child in calls:
        target = child.func
        names.append(target.attr if isinstance(target, ast.Attribute) else ast.unparse(target))
    return names


def _calls_port(node: ast.AST) -> bool:
    return any(name in rules.PORT_CALLS for name in _called_names(node))


def order_violations(stages_seen: list[str], where: str) -> list[Violation]:
    """Report stages out of order or a required stage missing from a run function."""
    expected = [
        s
        for s in rules.PIPELINE_STAGES
        if s in stages_seen or s not in rules.PIPELINE_OPTIONAL_STAGES
    ]
    if stages_seen != expected:
        return [Violation(where, 1, f"stages {stages_seen} must be {expected}")]
    return []


def _declared_stages(module: ast.Module) -> list[str]:
    for node in module.body:
        value = node.value if isinstance(node, ast.Assign) else None
        if isinstance(value, ast.Call) and ast.unparse(value.func) == STAGES_CLASS:
            names = [ast.unparse(k.value) for k in value.keywords]
            return [n for n in names if n in rules.PIPELINE_STAGES]
    return []


def _run_function(module: ast.Module) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == RUN_FUNCTION:
            return node
    return None


def run(root: Path) -> list[Violation]:
    """Check every pipeline.py in the capabilities tree."""
    violations = []
    for path in walk(root, CAPABILITIES):
        if path.name != "pipeline.py":
            continue
        module = parse(path)
        where = relative(path, root)
        entry = _run_function(module)
        if entry is None:
            violations.append(Violation(where, 1, "pipeline.py has no run function"))
            continue
        stages = _declared_stages(module) or [
            n for n in _called_names(entry) if n in rules.PIPELINE_STAGES
        ]
        violations += order_violations(stages, where)
        for node in module.body:
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.name != CALL_STAGE and _calls_port(node):
                message = f"{node.name} calls the port; only `call` may"
                violations.append(Violation(where, node.lineno, message))
    return violations
