"""ARCH-012 §3: a Protocol exists only at a substitution boundary named in the seams list."""

import ast
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

PROTOCOL = "Protocol"


def run(root: Path) -> list[Violation]:
    """Report every Protocol class whose name is not a seam."""
    violations = []
    for path in walk(root, rules.SRC):
        for node in ast.walk(parse(path)):
            if not isinstance(node, ast.ClassDef):
                continue
            bases = {ast.unparse(base) for base in node.bases}
            if PROTOCOL in bases and node.name not in rules.SEAMS:
                message = f"Protocol {node.name} is not a seam; substitute it or remove it"
                violations.append(Violation(relative(path, root), node.lineno, message))
    return violations
