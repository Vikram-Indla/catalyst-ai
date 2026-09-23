"""A threshold never loosens without a decision: a floor may not fall, a ceiling may not rise."""

from tools.checks import evals


def test_a_floor_that_falls_is_refused_and_one_that_rises_is_not() -> None:
    assert evals.loosened({"overall": 0.9}, {"overall": 0.8}, "overall: 0.8") == ["overall"]
    assert evals.loosened({"overall": 0.9}, {"overall": 0.95}, "overall: 0.95") == []


def test_a_latency_or_cost_ceiling_that_rises_is_refused() -> None:
    previous = {"p95_latency_ms": 800.0, "p95_cost_micros": 400.0}
    current = {"p95_latency_ms": 2000.0, "p95_cost_micros": 900.0}
    assert evals.loosened(previous, current, "") == ["p95_latency_ms", "p95_cost_micros"]


def test_a_ceiling_that_falls_is_a_tightening_and_passes() -> None:
    previous = {"p95_latency_ms": 2000.0}
    assert evals.loosened(previous, {"p95_latency_ms": 800.0}, "p95_latency_ms: 800") == []


def test_a_decision_in_the_file_allows_either() -> None:
    text = "# D-042\np95_latency_ms: 5000\n"
    assert evals.loosened({"p95_latency_ms": 800.0}, {"p95_latency_ms": 5000.0}, text) == []
