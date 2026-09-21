"""ARCH-011, RULE-001 §2: every file has one home; fixtures under tests/fixtures; no notebook."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

SOURCE_PACKAGES = ("contract", "config", "platform", "providers", "retrieval", "capabilities")
SOURCE_ROOT_FILES = frozenset({"__init__.py", "app.py", "cli.py", "py.typed"})
TEST_KINDS = ("architecture", "contract", "unit", "storage", "fixtures")
TEST_ROOT_FILES = frozenset({"conftest.py", "__init__.py"})
DATA_SUFFIXES = (".json", ".jsonl", ".txt", ".yaml", ".md", ".docx", ".pdf", ".pptx", ".csv")


def _source_violations(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    src = root / rules.SRC
    for path in walk(root, rules.SRC):
        parts = path.relative_to(src).parts
        if len(parts) == 1 and parts[0] not in SOURCE_ROOT_FILES:
            violations.append(Violation(relative(path, root), 1, "a root file that is not wiring"))
        elif len(parts) > 1 and parts[0] not in SOURCE_PACKAGES:
            violations.append(Violation(relative(path, root), 1, f"unknown package {parts[0]}"))
    for package in (src / "capabilities").glob("*/"):
        if package.name in rules.SKIP_DIRS or not package.is_dir():
            continue
        if not (package / "descriptor.py").exists():
            violations.append(
                Violation(relative(package, root), 1, "a capability package without descriptor.py")
            )
    return violations


def _test_violations(root: Path) -> list[Violation]:
    violations: list[Violation] = []
    tests = root / rules.TESTS
    if not tests.exists():
        return violations
    for path in walk(root, rules.TESTS, suffix=""):
        parts = path.relative_to(tests).parts
        if len(parts) == 1 and parts[0] not in TEST_ROOT_FILES:
            violations.append(
                Violation(relative(path, root), 1, "a test root file that is not conftest")
            )
        elif len(parts) > 1 and parts[0] not in TEST_KINDS:
            violations.append(Violation(relative(path, root), 1, f"unknown test kind {parts[0]}"))
        elif path.suffix in DATA_SUFFIXES and parts[0] != "fixtures":
            violations.append(
                Violation(relative(path, root), 1, "a data file outside tests/fixtures")
            )
    return violations


def _notebooks(root: Path) -> list[Violation]:
    return [
        Violation(relative(path, root), 1, "a notebook in the tree")
        for path in walk(root, Path(), suffix=".ipynb")
    ]


def _package_size_report(root: Path) -> None:
    for package in sorted((root / rules.SRC).rglob("*/")):
        files = [child for child in package.iterdir() if child.suffix == ".py"]
        if len(files) > rules.PACKAGE_SIZE_REPORT:
            print(
                f"report: {relative(package, root)} has {len(files)} files; split by responsibility"
            )


def run(root: Path) -> list[Violation]:
    """Report placement violations and notebooks; print package sizes over the report line."""
    if (root / rules.SRC).exists():
        _package_size_report(root)
    return _source_violations(root) + _test_violations(root) + _notebooks(root)
