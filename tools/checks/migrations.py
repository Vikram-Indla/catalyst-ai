"""ADR-006: migrations are forward-only, named and headed; every foreign key is indexed."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

FILE_NAME = re.compile(r"^\d{14}_[a-z0-9_]+\.sql$")
HEADER = re.compile(r"^-- migration: .+", re.M)
FORBIDDEN = ("DROP TABLE", "DROP COLUMN", "-- +goose Down", "DOWN")
FOREIGN_KEY = re.compile(r"^\s*(?P<column>\w+)\s+\w+.*\bREFERENCES\b", re.I | re.M)
INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX .* ON (?P<table>\w+)\s*\((?P<cols>[^)]*)\)", re.I)
CREATE_TABLE = re.compile(
    r"CREATE TABLE(?: IF NOT EXISTS)?\s+(?P<name>\w+)\s*\((?P<body>.*?)\);", re.S | re.I
)


def check(sql: str, name: str, where: str) -> list[Violation]:
    """Report naming, header, forbidden statements and unindexed foreign keys in one migration."""
    violations = []
    if not FILE_NAME.match(name):
        violations.append(Violation(where, 1, "migration name is not <timestamp>_<slug>.sql"))
    if not HEADER.search(sql):
        violations.append(Violation(where, 1, "migration lacks the `-- migration:` header"))
    for marker in FORBIDDEN:
        if marker.lower() in sql.lower():
            violations.append(Violation(where, 1, f"migration contains {marker!r}; forward-only"))
    indexed = {
        (m.group("table"), m.group("cols").split(",")[0].strip()) for m in INDEX.finditer(sql)
    }
    for table in CREATE_TABLE.finditer(sql):
        for fk in FOREIGN_KEY.finditer(table.group("body")):
            if (table.group("name"), fk.group("column")) not in indexed:
                violations.append(
                    Violation(
                        where,
                        1,
                        f"{table.group('name')}.{fk.group('column')} references without an index",
                    )
                )
    return violations


def run(root: Path) -> list[Violation]:
    """Check every migration file."""
    violations = []
    for path in walk(root, rules.MIGRATIONS, suffix=".sql"):
        violations += check(path.read_text(encoding="utf-8"), path.name, relative(path, root))
    return violations
