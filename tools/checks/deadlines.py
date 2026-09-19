"""RULE-002 §3: every IO client carries a deadline."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

CLIENT_CALLS = {
    "httpx.AsyncClient": "timeout",
    "httpx.Client": "timeout",
    "AsyncClient": "timeout",
    "asyncpg.connect": "timeout",
    "asyncpg.create_pool": "command_timeout",
    "create_pool": "command_timeout",
}


def run(root: Path) -> list[Violation]:
    """Report client constructions without their deadline keyword."""
    violations = []
    for path in walk(root, rules.SRC):
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func)
            keyword = CLIENT_CALLS.get(name)
            if keyword and not any(k.arg == keyword for k in node.keywords):
                violations.append(
                    Violation(relative(path, root), node.lineno, f"{name} without {keyword}=")
                )
    return violations
