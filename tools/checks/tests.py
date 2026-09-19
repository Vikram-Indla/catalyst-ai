"""RULE-002 §6, RULE-004 §2: every logic module has a test module; no mocking framework."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative, walk

MOCK_MODULES = ("unittest.mock", "mock", "pytest_mock")


def expected_test(module: Path, root: Path) -> Path:
    """Return the mirrored unit-test path for a source module."""
    rel = module.relative_to(root / rules.SRC)
    return root / rules.UNIT_TESTS / rel.parent / f"test_{rel.name}"


def _orphans(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.SRC):
        if path.name in rules.WIRING_MODULES:
            continue
        target = expected_test(path, root)
        if not target.exists():
            violations.append(
                Violation(relative(path, root), 1, f"no test module at {relative(target, root)}")
            )
    return violations


def _mocks(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.TESTS):
        for line, name in imported_names(parse(path)):
            if any(name == m or name.startswith(m + ".") for m in MOCK_MODULES):
                violations.append(
                    Violation(relative(path, root), line, "a mocking framework in a test")
                )
    return violations


def run(root: Path) -> list[Violation]:
    """Report source modules without a mirrored test and tests importing a mocking framework."""
    return _orphans(root) + _mocks(root)
