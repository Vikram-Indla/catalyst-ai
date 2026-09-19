"""RULE-002 §5: no inline clock, id or randomness outside the packages that own them."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk


def _allowed(path: Path, root: Path) -> bool:
    return any(path.is_relative_to(root / package) for package in rules.INLINE_ALLOWED_PACKAGES)


def run(root: Path) -> list[Violation]:
    """Report banned inline calls in src outside clock/ and ids/."""
    violations = []
    for path in walk(root, rules.SRC):
        if _allowed(path, root):
            continue
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                if name in rules.INLINE_BANNED_CALLS:
                    violations.append(
                        Violation(relative(path, root), node.lineno, f"inline {name}(); inject it")
                    )
    return violations
