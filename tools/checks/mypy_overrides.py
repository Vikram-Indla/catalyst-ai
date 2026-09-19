"""RULE-002 §1: mypy escape hatches exist only for SDKs imported under adapters and parsers."""

import configparser
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative, walk

MYPY_INI = Path("mypy.ini")
OVERRIDE_PREFIX = "mypy-"
ESCAPE = "ignore_missing_imports"


def overridden_packages(ini_text: str) -> set[str]:
    """Top-level package names with ignore_missing_imports set."""
    parser = configparser.ConfigParser()
    parser.read_string(ini_text)
    packages = set()
    for section in parser.sections():
        if section.startswith(OVERRIDE_PREFIX) and parser.getboolean(
            section, ESCAPE, fallback=False
        ):
            packages.add(section.removeprefix(OVERRIDE_PREFIX).split(".")[0])
    return packages


def _allowed(path: Path, root: Path) -> bool:
    return any(path.is_relative_to(root / package) for package in rules.UNTYPED_ALLOWED_PACKAGES)


def run(root: Path) -> list[Violation]:
    """Report an untyped SDK imported outside the packages that may contain it."""
    ini = root / MYPY_INI
    if not ini.exists():
        return []
    packages = overridden_packages(ini.read_text(encoding="utf-8"))
    violations = []
    for path in walk(root, rules.SRC):
        if _allowed(path, root):
            continue
        for line, name in imported_names(parse(path)):
            top = name.split(".")[0]
            if top in packages:
                message = f"untyped {top} imported outside adapters and parsers"
                violations.append(Violation(relative(path, root), line, message))
    return violations
