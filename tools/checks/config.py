"""RULE-003 §5: the environment is read only in config/; the ledger equals the settings class."""

import ast
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

SETTINGS_FILE = rules.SRC / "config" / "settings.py"
SETTINGS_CLASS = "Settings"
ENV_READS = ("os.environ", "os.getenv", "environ.get")
LEDGER_ROW = re.compile(r"^\| `(?P<name>[A-Z0-9_<>]+)` \|", re.MULTILINE)


def settings_fields(root: Path) -> set[str]:
    """Return the upper-cased field names of the Settings class."""
    path = root / SETTINGS_FILE
    if not path.exists():
        return set()
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.ClassDef) and node.name == SETTINGS_CLASS:
            return {
                statement.target.id.upper()
                for statement in node.body
                if isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id != "model_config"
            }
    return set()


def ledger_rows(text: str) -> set[str]:
    """Return the concrete variable names in the config ledger; parameterised rows are skipped."""
    return {
        m.group("name").split("__")[0]
        for m in LEDGER_ROW.finditer(text)
        if "<" not in m.group("name")
    }


def _environment_reads(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.SRC):
        if path.parent == root / rules.SRC / "config":
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if any(marker in line for marker in ENV_READS):
                violations.append(
                    Violation(relative(path, root), number, "reads the environment outside config/")
                )
    return violations


def ledger_violations(fields: set[str], rows: set[str], where: str) -> list[Violation]:
    """Report fields without a row and rows without a field."""
    violations = [
        Violation(where, 1, f"{name} is a setting without a ledger row")
        for name in sorted(fields - rows)
    ]
    violations += [
        Violation(where, 1, f"{name} is a ledger row without a setting")
        for name in sorted(rows - fields)
    ]
    return violations


def run(root: Path) -> list[Violation]:
    """Report environment reads outside config/ and ledger drift."""
    ledger = root / rules.CONFIG_LEDGER
    rows = ledger_rows(ledger.read_text(encoding="utf-8")) if ledger.exists() else set()
    return _environment_reads(root) + ledger_violations(
        settings_fields(root), rows, rules.CONFIG_LEDGER.as_posix()
    )
