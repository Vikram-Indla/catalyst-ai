"""RULE-001 §4, ARCH-011 §3: banned stems, banned suffixes, capability names that agree."""

import ast
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, python_files, relative

DESCRIPTOR_NAME = re.compile(r'^\s*name\s*=\s*"(?P<name>[a-z0-9-]+)"', re.MULTILINE)


def _stem_violations(root: Path) -> list[Violation]:
    violations = []
    for path in python_files(root):
        stem = path.stem
        banned = stem in rules.BANNED_STEMS
        if stem == rules.MODELS_FILE[:-3] and path.parent.parent.name == "providers":
            banned = False
        if banned:
            violations.append(Violation(relative(path, root), 1, f"banned file stem {stem!r}"))
        if path.name == "__init__.py" and path.parent.name in rules.BANNED_STEMS:
            violations.append(
                Violation(relative(path, root), 1, f"banned package name {path.parent.name!r}")
            )
    return violations


def _suffix_violations(root: Path) -> list[Violation]:
    violations = []
    for path in python_files(root):
        for node in ast.walk(parse(path)):
            if isinstance(node, ast.ClassDef) and node.name.endswith(rules.BANNED_SUFFIXES):
                if node.name in rules.SEAMS or node.name.endswith("Middleware"):
                    continue
                message = f"class {node.name} carries a suffix that says nothing"
                violations.append(Violation(relative(path, root), node.lineno, message))
    return violations


def _capability_violations(root: Path) -> list[Violation]:
    violations = []
    for descriptor in sorted((root / rules.SRC / "capabilities").glob("*/descriptor.py")):
        match = DESCRIPTOR_NAME.search(descriptor.read_text(encoding="utf-8"))
        package = descriptor.parent.name
        if match is None:
            violations.append(Violation(relative(descriptor, root), 1, "descriptor without a name"))
        elif match.group("name").replace("-", "_") != package:
            message = f"capability {match.group('name')!r} does not match package {package!r}"
            violations.append(Violation(relative(descriptor, root), 1, message))
    return violations


def run(root: Path) -> list[Violation]:
    """Report banned stems and suffixes, and capability names that disagree with their package."""
    return _stem_violations(root) + _suffix_violations(root) + _capability_violations(root)
