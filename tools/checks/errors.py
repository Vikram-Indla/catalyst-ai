"""RULE-003 §2: every code is declared and raised; no SDK exception escapes an adapter."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

CATALOG = rules.SRC / "contract" / "errors.py"
ENUM_NAME = "ErrorCode"
PLATFORM_RAISERS = frozenset({"AUTH_INVALID", "VALIDATION_INVALID_INPUT", "INTERNAL_ERROR"})
ROUTING_CODES = frozenset({"CAPABILITY_UNKNOWN"})
SDK_EXCEPTION_MARKERS = ("httpx.", "HTTPStatusError", "ConnectError", "ReadTimeout")


def declared_codes(root: Path) -> dict[str, int]:
    """Return the enum members of the catalog with their line numbers."""
    catalog = root / CATALOG
    if not catalog.exists():
        return {}
    for node in ast.walk(parse(catalog)):
        if isinstance(node, ast.ClassDef) and node.name == ENUM_NAME:
            return {
                target.id: statement.lineno
                for statement in node.body
                if isinstance(statement, ast.Assign)
                for target in statement.targets
                if isinstance(target, ast.Name)
            }
    return {}


def referenced_codes(root: Path) -> set[str]:
    """Every `ErrorCode.X` referenced anywhere in src outside the catalog."""
    found = set()
    for path in walk(root, rules.SRC):
        if path == root / CATALOG:
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Attribute) and getattr(node.value, "id", None) == ENUM_NAME:
                found.add(node.attr)
    return found


def _escaping_sdk_exceptions(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.SRC):
        inside_adapter = path.parent.parent == root / rules.SRC / "providers"
        if inside_adapter:
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                text = ast.unparse(node.type)
                if any(marker in text for marker in SDK_EXCEPTION_MARKERS):
                    violations.append(
                        Violation(
                            relative(path, root),
                            node.lineno,
                            f"handles an SDK exception {text} outside an adapter",
                        )
                    )
    return violations


def run(root: Path) -> list[Violation]:
    """Report declared-but-unraised codes outside the platform set, and SDK exceptions escaping."""
    declared = declared_codes(root)
    referenced = referenced_codes(root)
    where = CATALOG.as_posix()
    violations = []
    capabilities_exist = any((root / rules.SRC / "capabilities").glob("*/descriptor.py"))
    for name, line in declared.items():
        if name in PLATFORM_RAISERS or name in ROUTING_CODES or name in referenced:
            continue
        if capabilities_exist:
            violations.append(Violation(where, line, f"{name} is declared but nothing raises it"))
    return violations + _escaping_sdk_exceptions(root)
