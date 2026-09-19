"""ARCH-008 §1: the measured p95 latency and cost of every capability sit under its descriptor."""

import json
from pathlib import Path

from tools import rules
from tools.checks.capabilities import read_descriptor
from tools.checks.gate import Violation

RUNS = Path(".evals")
LATENCY_FIELD = "p95_latency_ms"
COST_FIELD = "p95_cost_micros"


def check(declared: dict[str, object], measured: dict[str, float], where: str) -> list[Violation]:
    """Report a measurement over its declaration."""
    violations = []
    for key in (LATENCY_FIELD, COST_FIELD):
        limit = declared.get(key)
        value = measured.get(key)
        if isinstance(limit, int | float) and isinstance(value, int | float) and value > limit:
            violations.append(
                Violation(where, 1, f"{key} measured {value} over the declared {limit}")
            )
    return violations


def run(root: Path) -> list[Violation]:
    """Compare each capability's last eval run with its descriptor; a missing run is red."""
    violations = []
    for path in sorted((root / rules.SRC / "capabilities").glob("*/descriptor.py")):
        descriptor = read_descriptor(path, root)
        run_file = root / RUNS / f"{descriptor.values.get('name', '')}.json"
        if not run_file.exists():
            violations.append(
                Violation(descriptor.path, 1, "no eval run recorded; run `make evals`")
            )
            continue
        measured = json.loads(run_file.read_text(encoding="utf-8"))
        violations += check(descriptor.values, measured, descriptor.path)
    return violations
