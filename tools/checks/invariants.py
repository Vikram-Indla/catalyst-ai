"""RULE-000 §6: every registry row names a check that exists; every architecture test is claimed."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, walk

ROW = re.compile(r"^\| INV-\d{3} \|(?P<cells>.*)\|$", re.M)
CHECK_REF = re.compile(r"tools/checks/(?P<name>[a-z_]+)")
TEST_REF = re.compile(r"\b(?P<name>test_[a-z0-9_]+)\b")
TEST_DEF = re.compile(r"^(?:async )?def (?P<name>test_[a-z0-9_]+)\(", re.M)


def references(registry: str) -> tuple[set[str], set[str]]:
    """Return the check names and test names the registry's enforcement column mentions."""
    checks: set[str] = set()
    tests: set[str] = set()
    for row in ROW.finditer(registry):
        cells = row.group("cells")
        checks |= {m.group("name") for m in CHECK_REF.finditer(cells)}
        tests |= {m.group("name") for m in TEST_REF.finditer(cells)}
    return checks, tests


def check(
    registry: str, existing_checks: set[str], existing_tests: set[str], where: str
) -> list[Violation]:
    """Report references to missing checks or tests, and tests no row claims."""
    checks, tests = references(registry)
    violations = [
        Violation(where, 1, f"names tools/checks/{name}, which does not exist")
        for name in sorted(checks - existing_checks)
    ]
    violations += [
        Violation(where, 1, f"names {name}, which no architecture test defines")
        for name in sorted(tests - existing_tests)
    ]
    violations += [
        Violation(rules.ARCHITECTURE_TESTS.as_posix(), 1, f"{name} is claimed by no registry row")
        for name in sorted(existing_tests - tests)
    ]
    return violations


def run(root: Path) -> list[Violation]:
    """Read the registry, the check modules and the architecture tests."""
    registry = root / rules.INVARIANTS
    if not registry.exists():
        return [Violation(rules.INVARIANTS.as_posix(), 1, "no invariants registry")]
    checks = {
        p.stem for p in (root / rules.TOOLS / "checks").glob("*.py") if not p.stem.startswith("_")
    }
    tests: set[str] = set()
    for path in walk(root, rules.ARCHITECTURE_TESTS):
        tests |= {m.group("name") for m in TEST_DEF.finditer(path.read_text(encoding="utf-8"))}
    return check(registry.read_text(encoding="utf-8"), checks, tests, rules.INVARIANTS.as_posix())
