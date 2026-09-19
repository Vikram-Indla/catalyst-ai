"""RULE-007: a session that changed code left a record with the matrix, the gate and the numbers."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation
from tools.checks.gitinfo import changed_since_main

CODE_PREFIXES = ("src/", "tools/", "tests/", "evals/", "db/", "api/")
REQUIRED_SECTIONS = ("## Impact matrix", "$ make verify", "$ make ci")
EVAL_SECTION = "## Eval and budget numbers"


def check(changed: list[str], records: dict[str, str]) -> list[Violation]:
    """Given changed files and the changed records' texts, report a missing or incomplete record."""
    if not any(path.startswith(CODE_PREFIXES) for path in changed):
        return []
    if not records:
        return [Violation(rules.SESSIONS.as_posix(), 1, "code changed without a session record")]
    violations = []
    for path, text in records.items():
        for section in REQUIRED_SECTIONS:
            if section not in text:
                violations.append(Violation(path, 1, f"record lacks {section!r}"))
        touches_capability = any(p.startswith(rules.CAPABILITY_PATHS) for p in changed)
        if touches_capability and EVAL_SECTION not in text:
            violations.append(Violation(path, 1, "a capability changed without the eval numbers"))
    return violations


def run(root: Path) -> list[Violation]:
    """Read the branch's changed files and its changed session records."""
    changed = changed_since_main(root)
    prefix = rules.SESSIONS.as_posix() + "/"
    records = {
        path: (root / path).read_text(encoding="utf-8")
        for path in changed
        if path.startswith(prefix)
        and not path.endswith("_TEMPLATE-session.md")
        and (root / path).exists()
    }
    return check(changed, records)
