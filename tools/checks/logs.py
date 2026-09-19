"""ARCH-010 §1: no content-shaped key in a logging call."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical", "log"})


def _is_logging_call(call: ast.Call) -> bool:
    return isinstance(call.func, ast.Attribute) and call.func.attr in LOG_METHODS


def _content_keys(call: ast.Call) -> list[str]:
    keys = []
    for keyword in call.keywords:
        if keyword.arg in rules.CONTENT_LOG_KEYS:
            keys.append(keyword.arg)
        if keyword.arg == "extra" and isinstance(keyword.value, ast.Dict):
            for key in keyword.value.keys:
                if (
                    isinstance(key, ast.Constant)
                    and str(key.value).lower() in rules.CONTENT_LOG_KEYS
                ):
                    keys.append(str(key.value))
    for argument in call.args:
        if isinstance(argument, ast.JoinedStr):
            keys.append("f-string")
    return keys


def run(root: Path) -> list[Violation]:
    """Report every logging call carrying a content key or an interpolated message."""
    violations = []
    for path in walk(root, rules.SRC):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Call) and _is_logging_call(node):
                for key in _content_keys(node):
                    violations.append(
                        Violation(relative(path, root), node.lineno, f"logging call carries {key}")
                    )
    return violations
