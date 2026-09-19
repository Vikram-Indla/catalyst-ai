"""RULE-009 §5: a temporary flag names its removal ticket and an expiry that has not passed."""

import re
from datetime import UTC, date, datetime
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

SETTINGS_FILE = rules.SRC / "config" / "settings.py"
FLAG = re.compile(r"FLAG\s*·\s*(?P<ticket>AI-\d{3})\s*·\s*(?P<expires>\d{4}-\d{2}-\d{2})")
FLAG_MARKER = "FLAG"


def check(settings_text: str, today: date, where: str) -> list[Violation]:
    """Report flag descriptions without ticket and date, or past their date."""
    violations = []
    for number, line in enumerate(settings_text.splitlines(), start=1):
        if FLAG_MARKER not in line or "description=" not in line:
            continue
        match = FLAG.search(line)
        if match is None:
            violations.append(
                Violation(
                    where, number, "a flag without `FLAG · AI-NNN · YYYY-MM-DD` in its description"
                )
            )
        elif date.fromisoformat(match.group("expires")) < today:
            violations.append(
                Violation(
                    where,
                    number,
                    f"flag expired on {match.group('expires')}; remove it, {match.group('ticket')}",
                )
            )
    return violations


def run(root: Path) -> list[Violation]:
    """Read the settings module."""
    path = root / SETTINGS_FILE
    if not path.exists():
        return []
    return check(
        path.read_text(encoding="utf-8"), datetime.now(tz=UTC).date(), SETTINGS_FILE.as_posix()
    )
