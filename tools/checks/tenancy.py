"""ARCH-006 §1, ARCH-008 §3: tenant tables carry organization_id and RLS; queries are scoped."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative, walk

CREATE_TABLE = re.compile(
    r"CREATE TABLE(?: IF NOT EXISTS)?\s+(?P<name>\w+)\s*\((?P<body>.*?)\);", re.S | re.I
)
ENABLE_RLS = "ENABLE ROW LEVEL SECURITY"
CREATE_POLICY = "CREATE POLICY"
ORG_COLUMN = "organization_id"
ORG_INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX .* ON (?P<table>\w+)\s*\((?P<cols>[^)]*)\)", re.I)
CACHE_KEY_MARKER = "def cache_key("


def tenant_tables(sql: str) -> dict[str, str]:
    """Every table whose body declares organization_id, with its body text."""
    return {
        m.group("name"): m.group("body")
        for m in CREATE_TABLE.finditer(sql)
        if ORG_COLUMN in m.group("body")
    }


def migration_violations(sql: str, where: str) -> list[Violation]:
    """Report tenant tables without NOT NULL, an index, RLS or a policy."""
    violations = []
    indexed = {m.group("table") for m in ORG_INDEX.finditer(sql) if ORG_COLUMN in m.group("cols")}
    for table, body in tenant_tables(sql).items():
        column = next((line for line in body.splitlines() if ORG_COLUMN in line), "")
        if "NOT NULL" not in column.upper():
            violations.append(Violation(where, 1, f"{table}.{ORG_COLUMN} is nullable"))
        if table not in indexed:
            violations.append(Violation(where, 1, f"{table}.{ORG_COLUMN} is not indexed"))
        if f"ALTER TABLE {table} {ENABLE_RLS}".lower() not in sql.lower():
            violations.append(Violation(where, 1, f"{table} has no row level security"))
        if not re.search(rf"{CREATE_POLICY}\s+\w+\s+ON\s+{table}\b", sql, re.I):
            violations.append(Violation(where, 1, f"{table} has no policy"))
    return violations


def query_violations(sql: str, tables: set[str], where: str) -> list[Violation]:
    """Report statements on a tenant table that do not mention organization_id."""
    violations = []
    for number, statement in enumerate(filter(None, (s.strip() for s in sql.split(";"))), start=1):
        touched = [t for t in tables if re.search(rf"\b{t}\b", statement)]
        if touched and ORG_COLUMN not in statement:
            violations.append(
                Violation(where, number, f"statement on {touched[0]} without {ORG_COLUMN}")
            )
    return violations


def run(root: Path) -> list[Violation]:
    """Read every migration and every query file."""
    violations = []
    tables: set[str] = set()
    for migration in walk(root, rules.MIGRATIONS, suffix=".sql"):
        sql = migration.read_text(encoding="utf-8")
        tables |= set(tenant_tables(sql))
        violations += migration_violations(sql, relative(migration, root))
    for query in walk(root, rules.QUERIES, suffix=".sql"):
        violations += query_violations(
            query.read_text(encoding="utf-8"), tables, relative(query, root)
        )
    return violations
