"""RULE-006 §1 step 4: every check is proven red on a planted violation, one line per check."""

from collections.abc import Callable
from datetime import date
from pathlib import Path

from tools.checks import (
    budgets,
    changelog,
    ci,
    commits,
    coverage,
    deprecations,
    deps,
    evals,
    flags,
    gate,
    invariants,
    journeys,
    licenses,
    openapi,
    prclass,
    sessions,
)
from tools.checks.gate import Violation
from tools.checks.gitinfo import Commit

PLANTS = Path(__file__).parent / "plants"
FAR_PAST = date(2020, 1, 1)
LOW_COVERAGE = {
    "files": {"src/catalyst_ai/config/a.py": {"summary": {"percent_covered": 50.0}}},
    "totals": {"percent_covered": 50.0},
}
DEPRECATED_DOCUMENT = {"paths": {"/v1/old": {"post": {"deprecated": True}}}}
BAD_REGISTRY = "| INV-001 | x | o | `tools/checks/nope` | C | S |"

VALUE_PLANTS: dict[str, Callable[[], list[Violation]]] = {
    "openapi": lambda: (
        openapi.drift_violations({"a": 1}, {"a": 2}, "w")
        + openapi.operation_violations({"paths": {"/x": {"get": {}}}}, "w")
    ),
    "changelog": lambda: changelog.check(["api/openapi.yaml"]),
    "deps": lambda: deps.check({"leftpad"}, set()),
    "licenses": lambda: licenses.check([("evil", "AGPL-3.0")]),
    "ci": lambda: ci.check("      - run: echo hi\n", "w"),
    "commits": lambda: commits.check(
        [Commit("abc123def456", "x", ("uv.lock", "src/catalyst_ai/x.py"))]
    ),
    "sessions": lambda: sessions.check(["src/catalyst_ai/x.py"], {}),
    "prclass": lambda: prclass.check(
        ["src/catalyst_ai/contract/envelopes.py"], {"r.md": "Blast radius: LOCAL"}
    ),
    "invariants": lambda: invariants.check(BAD_REGISTRY, set(), set(), "w"),
    "evals": lambda: (
        [Violation("w", 1, k) for k in evals.lowered({"a": 0.8}, {"a": 0.7}, "a: 0.7")]
        + evals.set_violations([], "w")
    ),
    "budgets": lambda: budgets.check({"p95_latency_ms": 100}, {"p95_latency_ms": 200.0}, "w"),
    "deprecations": lambda: deprecations.check(DEPRECATED_DOCUMENT, FAR_PAST, "w"),
    "flags": lambda: flags.check(
        'x = Field(description="FLAG · AI-001 · 2020-01-01")', date(2026, 1, 1), "w"
    ),
    "journeys": lambda: journeys.check({"foo.run": ["ai.x.y"]}, set(), ""),
    "coverage": lambda: coverage.check(LOW_COVERAGE),
}


def prove(name: str) -> tuple[bool, int]:
    """Run one check on its plant; red is the pass."""
    if name in VALUE_PLANTS:
        found = VALUE_PLANTS[name]()
    else:
        plant = PLANTS / name
        if not plant.is_dir():
            return False, 0
        found = gate.run_check(name, plant)
    return bool(found), len(found)


def main() -> int:
    """Prove every check red on its plant and print one line per check."""
    failures = 0
    for name in gate.CHECKS:
        red, count = prove(name)
        print(f"{'red ' if red else 'NOT RED'} {name} ({count} on plant)")
        failures += 0 if red else 1
    print(f"selftest: {len(gate.CHECKS) - failures}/{len(gate.CHECKS)} checks red on their plant")
    return 1 if failures else 0
