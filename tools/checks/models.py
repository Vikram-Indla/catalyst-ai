"""ARCH-005 §2: a concrete model id lives only in the register, and the register pins stable ids.

Outside an adapter's `models.py` no model id may appear at all. Inside it, an id that moves
(`-latest`) or may change or vanish (`-preview`, `-exp`) is refused, because a recorded fixture
keyed to it would stop meaning what it meant.
"""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

PATTERNS = tuple(re.compile(p) for p in rules.MODEL_ID_PATTERNS)
UNSTABLE = re.compile(rules.UNSTABLE_MODEL_ID)
QUOTED_ID = re.compile(r"\"([a-z][a-z0-9.-]*)\"")


def _allowed(path: Path, root: Path) -> bool:
    providers = root / rules.SRC / "providers"
    return path.name == rules.MODELS_FILE and path.parent.parent == providers


def run(root: Path) -> list[Violation]:
    """Report a model-id literal anywhere in src or tests outside the adapters' models.py."""
    violations = []
    for path in walk(root, rules.SRC, rules.TESTS):
        if _allowed(path, root):
            violations += _unstable(path, root)
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(pattern.search(line) for pattern in PATTERNS):
                violations.append(
                    Violation(
                        relative(path, root), number, "a concrete model id outside the register"
                    )
                )
    return violations


def _unstable(path: Path, root: Path) -> list[Violation]:
    """Report a moving or preview id among the quoted ids of a register file."""
    violations = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for model_id in QUOTED_ID.findall(line):
            if any(p.search(model_id) for p in PATTERNS) and UNSTABLE.search(model_id):
                violations.append(
                    Violation(relative(path, root), number, f"{model_id} is not a pinned stable id")
                )
    return violations
