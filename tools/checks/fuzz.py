"""RULE-004 §2: every parser and chunker has a property test."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

PROPERTY_SUFFIX = "_property.py"
HYPOTHESIS = "hypothesis"


def _is_parser(path: Path, root: Path) -> bool:
    rel = relative(path, root)
    return any(marker in rel for marker in rules.PARSER_MARKERS) and path.name != "__init__.py"


def run(root: Path) -> list[Violation]:
    """Report parser modules without a hypothesis-based property test."""
    violations = []
    for path in walk(root, rules.SRC):
        if not _is_parser(path, root):
            continue
        rel = path.relative_to(root / rules.SRC)
        target = root / rules.UNIT_TESTS / rel.parent / f"test_{rel.stem}{PROPERTY_SUFFIX}"
        if not target.exists() or HYPOTHESIS not in target.read_text(encoding="utf-8"):
            violations.append(
                Violation(
                    relative(path, root),
                    1,
                    f"parser without a property test at {relative(target, root)}",
                )
            )
    return violations
