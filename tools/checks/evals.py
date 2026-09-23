"""ADR-005, RULE-008 §3: sets carry injection cases; a threshold never loosens without a decision.

A score is a floor, so loosening it is a fall. A latency or cost budget is a ceiling, so
loosening it is a rise, and tightening it (a lower number) needs no decision.
"""

import json
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative
from tools.checks.gitinfo import MAIN, git_output

THRESHOLD = re.compile(r"^(?P<key>[a-z0-9_]+):\s*(?P<value>[0-9.]+)\s*$", re.M)
DECISION = re.compile(r"\bD-\d{3}\b")
INJECTION_TAG = "injection"
CEILINGS = frozenset({"p95_latency_ms", "p95_cost_micros"})


def thresholds(text: str) -> dict[str, float]:
    """Parse the flat `key: number` lines of a thresholds file."""
    return {m.group("key"): float(m.group("value")) for m in THRESHOLD.finditer(text)}


def loosened(previous: dict[str, float], current: dict[str, float], current_text: str) -> list[str]:
    """Keys whose floor fell or whose ceiling rose, without a D-NNN reference in the file."""
    if DECISION.search(current_text):
        return []
    return [
        key
        for key, value in current.items()
        if key in previous and (value > previous[key] if key in CEILINGS else value < previous[key])
    ]


def _tagged(case: dict[str, object]) -> bool:
    tags = case.get("tags")
    return isinstance(tags, list) and INJECTION_TAG in tags


def set_violations(cases: list[dict[str, object]], where: str) -> list[Violation]:
    """Report a set without an injection-tagged case."""
    tagged = any(_tagged(case) for case in cases)
    return [] if tagged else [Violation(where, 1, "the set has no case tagged injection")]


def run(root: Path) -> list[Violation]:
    """Check every eval set against its own content and its previous thresholds on main."""
    violations: list[Violation] = []
    evals = root / rules.EVALS
    if not evals.is_dir():
        return violations
    for directory in sorted(p for p in evals.iterdir() if p.is_dir()):
        set_file = directory / "set.jsonl"
        if set_file.exists():
            cases = [
                json.loads(line)
                for line in set_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            violations += set_violations(cases, relative(set_file, root))
        threshold_file = directory / "thresholds.yaml"
        if threshold_file.exists():
            current_text = threshold_file.read_text(encoding="utf-8")
            previous_text = (
                git_output(root, "show", f"{MAIN}:{relative(threshold_file, root)}") or ""
            )
            for key in loosened(thresholds(previous_text), thresholds(current_text), current_text):
                violations.append(
                    Violation(
                        relative(threshold_file, root),
                        1,
                        f"threshold {key} loosened without a D-NNN",
                    )
                )
    return violations
