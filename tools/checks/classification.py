"""ARCH-002 §3: every request field declares a data class; none is RESTRICTED."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

REQUEST_SUFFIXES = ("Request", "RequestEnvelope")
EXTRA_KEY = "json_schema_extra"
CLASSIFIED_CALL = "classified"


def _data_class_of(annotation: ast.expr) -> str | None:
    for node in ast.walk(annotation):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == CLASSIFIED_CALL:
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return first.value
        if (
            isinstance(node, ast.keyword)
            and node.arg == EXTRA_KEY
            and isinstance(node.value, ast.Dict)
        ):
            for key, value in zip(node.value.keys, node.value.values, strict=True):
                if isinstance(key, ast.Constant) and key.value == "data_class":
                    inner = value.value if isinstance(value, ast.Constant) else None
                    return inner if isinstance(inner, str) else None
    return None


def _is_request(node: ast.ClassDef) -> bool:
    return node.name.endswith(REQUEST_SUFFIXES)


def _field_violations(path: Path, root: Path, node: ast.ClassDef) -> list[Violation]:
    violations = []
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        if statement.target.id == "model_config":
            continue
        data_class = _data_class_of(statement.annotation)
        where = relative(path, root)
        if data_class is None:
            message = f"{node.name}.{statement.target.id} declares no data class"
            violations.append(Violation(where, statement.lineno, message))
        elif data_class == rules.RESTRICTED:
            message = f"{node.name}.{statement.target.id} is RESTRICTED; no such field may exist"
            violations.append(Violation(where, statement.lineno, message))
        elif data_class not in rules.DATA_CLASSES:
            message = f"{node.name}.{statement.target.id} has unknown data class {data_class!r}"
            violations.append(Violation(where, statement.lineno, message))
    return violations


def run(root: Path) -> list[Violation]:
    """Report unclassified or RESTRICTED fields on every request model of the contract."""
    violations = []
    for path in walk(root, rules.SRC / "contract"):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.ClassDef) and _is_request(node):
                violations.extend(_field_violations(path, root, node))
    return violations
