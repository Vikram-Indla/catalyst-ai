"""ARCH-005 §2: a concrete model id lives only in the register and an adapter's models.py."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

PATTERNS = tuple(re.compile(p) for p in rules.MODEL_ID_PATTERNS)


def _allowed(path: Path, root: Path) -> bool:
    providers = root / rules.SRC / "providers"
    return path.name == rules.MODELS_FILE and path.parent.parent == providers


def run(root: Path) -> list[Violation]:
    """Report a model-id literal anywhere in src or tests outside the adapters' models.py."""
    violations = []
    for path in walk(root, rules.SRC, rules.TESTS):
        if _allowed(path, root):
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                violations.append(
                    Violation(
                        relative(path, root), number, "a concrete model id outside the register"
                    )
                )
    return violations
