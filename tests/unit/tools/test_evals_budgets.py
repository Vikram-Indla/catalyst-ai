"""The commit-time eval run judges every grader floor; the timing and cost budgets wait for the gate."""

from tools.evals import judge

FLOORS = {
    "schema_valid": 1.0,
    "overall": 0.97,
    "p95_latency_ms": 15_000.0,
    "p95_cost_micros": 1_000.0,
}


def result(overall: float, latency: float, cost: float) -> dict[str, object]:
    return {
        "scores": {"schema_valid": overall},
        "overall": overall,
        "p95_latency_ms": latency,
        "p95_cost_micros": cost,
    }


def test_the_full_gate_enforces_the_budgets() -> None:
    reds = judge(result(1.0, 15_341.0, 1_200.0), FLOORS)
    assert reds == ["p95_latency_ms 15341 > 15000.0", "p95_cost_micros 1200 > 1000.0"]


def test_the_commit_time_run_reports_the_budgets_but_never_fails_on_them() -> None:
    assert judge(result(1.0, 15_341.0, 1_200.0), FLOORS, budgets=False) == []


def test_the_commit_time_run_still_fails_on_a_grader_floor() -> None:
    assert judge(result(0.5, 10.0, 10.0), FLOORS, budgets=False) == [
        "schema_valid 0.500 < 1.0",
        "overall 0.500 < 0.97",
    ]
