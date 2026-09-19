"""RULE-004 §1: coverage floors per layer, classified by path; overall 90."""

import json
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

REPORT = Path("coverage.json")


def floor_for(path: str) -> float | None:
    """Return the floor of the first matching prefix; None when the path is excluded."""
    if path.startswith(rules.COVERAGE_EXCLUDED):
        return None
    for prefix, floor in rules.COVERAGE_FLOORS:
        if path.startswith(prefix):
            return floor
    return rules.COVERAGE_OVERALL


def check(report: dict[str, object]) -> list[Violation]:
    """Report every file under its floor and an overall under the repository floor."""
    violations = []
    files = report.get("files", {})
    if isinstance(files, dict):
        for raw_path, data in sorted(files.items()):
            path = raw_path.replace("\\", "/")
            floor = floor_for(path)
            summary = data.get("summary", {}) if isinstance(data, dict) else {}
            percent = float(summary.get("percent_covered", 0.0))
            if floor is not None and percent < floor:
                violations.append(
                    Violation(path, 1, f"coverage {percent:.1f}% under the floor {floor:.0f}%")
                )
    totals = report.get("totals", {})
    overall = float(totals.get("percent_covered", 0.0)) if isinstance(totals, dict) else 0.0
    if overall < rules.COVERAGE_OVERALL:
        violations.append(
            Violation(
                REPORT.as_posix(),
                1,
                f"overall coverage {overall:.1f}% under {rules.COVERAGE_OVERALL:.0f}%",
            )
        )
    return violations


def run(root: Path) -> list[Violation]:
    """Read the coverage.json the test step wrote."""
    path = root / REPORT
    if not path.exists():
        return [Violation(REPORT.as_posix(), 1, "no coverage report; run `make test` first")]
    return check(json.loads(path.read_text(encoding="utf-8")))
