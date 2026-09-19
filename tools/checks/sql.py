"""ADR-006: SQL lives only in the query files; no SELECT *."""

import ast
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

SQL_START = re.compile(
    r"^\s*(SELECT\b.*\bFROM\b|INSERT\s+INTO\b|UPDATE\s+\w+\s+SET\b|DELETE\s+FROM\b"
    r"|CREATE\s+(TABLE|INDEX|POLICY)\b|ALTER\s+TABLE\b|DROP\s+TABLE\b|WITH\s+\w+\s+AS\s*\()",
    re.I | re.S,
)
SELECT_STAR = re.compile(r"\bSELECT\s+\*", re.I)


def run(root: Path) -> list[Violation]:
    """Report SQL string literals outside the query files and SELECT * anywhere."""
    violations = []
    for path in walk(root, rules.SRC):
        if path.parent == root / rules.QUERIES:
            continue
        for node in ast.walk(parse(path)):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and SQL_START.match(node.value)
            ):
                violations.append(
                    Violation(relative(path, root), node.lineno, "SQL outside the query files")
                )
    for query in walk(root, rules.QUERIES, suffix=".sql") + walk(
        root, rules.MIGRATIONS, suffix=".sql"
    ):
        for number, line in enumerate(query.read_text(encoding="utf-8").splitlines(), start=1):
            if SELECT_STAR.search(line):
                violations.append(Violation(relative(query, root), number, "SELECT *"))
    return violations
