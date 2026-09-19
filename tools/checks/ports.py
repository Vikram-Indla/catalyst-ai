"""RULE-003 §3: the port's models are pydantic and builtins; no SDK or httpx type crosses it."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative

ALLOWED_TOP_LEVEL = frozenset(
    {"collections", "enum", "typing", "uuid", "datetime", "pydantic", "catalyst_ai", "__future__"}
)
ALLOWED_INTERNAL = ("catalyst_ai.contract",)


def run(root: Path) -> list[Violation]:
    """Report any import in port.py outside the allowed set."""
    port = root / rules.SRC / "providers" / "port.py"
    if not port.exists():
        return []
    violations = []
    for line, name in imported_names(parse(port)):
        top = name.split(".")[0]
        internal_ok = not name.startswith("catalyst_ai") or name.startswith(ALLOWED_INTERNAL)
        if top not in ALLOWED_TOP_LEVEL or not internal_ok:
            violations.append(Violation(relative(port, root), line, f"the port imports {name}"))
    return violations
