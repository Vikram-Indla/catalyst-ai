"""RULE-009 §3: a deprecated operation names its replacement and a sunset that has not passed."""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from tools import api, rules
from tools.checks.gate import Violation

SUNSET = "x-sunset"
REPLACEMENT = "x-replacement"


def check(document: dict[str, Any], today: date, where: str) -> list[Violation]:
    """Report deprecated operations without replacement or sunset, or past their sunset."""
    violations = []
    for path, item in document.get("paths", {}).items():
        for method, operation in item.items():
            if not operation.get("deprecated"):
                continue
            label = f"{method.upper()} {path}"
            if REPLACEMENT not in operation:
                violations.append(
                    Violation(where, 1, f"{label} is deprecated without {REPLACEMENT}")
                )
            sunset = operation.get(SUNSET)
            if sunset is None:
                violations.append(Violation(where, 1, f"{label} is deprecated without {SUNSET}"))
            elif date.fromisoformat(str(sunset)) < today:
                violations.append(Violation(where, 1, f"{label} survived its sunset {sunset}"))
    return violations


def run(root: Path) -> list[Violation]:
    """Check the committed document against today's date."""
    target = root / rules.API_DOCUMENT
    if not target.exists():
        return []
    return check(api.load(target), datetime.now(tz=UTC).date(), rules.API_DOCUMENT.as_posix())
