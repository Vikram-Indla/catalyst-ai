"""Each latency alert fires at the budget its capability declares, never at one number for all."""

from pathlib import Path

import yaml

from tools.checks import latency

EDGES = {0.8, 4.0, 8.0}
ONE_SECOND = 1.0


def _committed() -> list[latency.LatencyRule]:
    document = yaml.safe_load(Path("ops/alerts.yaml").read_text(encoding="utf-8"))
    return latency.latency_rules(document, latency.REQUEST_SERIES, "operation")


def _rule(selector: str, threshold: float) -> dict[str, object]:
    series = f'{latency.REQUEST_SERIES}{{operation=~"{selector}"}}'
    return {
        "alert": "Planted",
        "expr": f"histogram_quantile(0.95, rate({series}[1h])) > {threshold}",
    }


def _planted(*rules: dict[str, object]) -> list[latency.LatencyRule]:
    document = {"groups": [{"rules": list(rules)}]}
    return latency.latency_rules(document, latency.REQUEST_SERIES, "operation")


def test_the_committed_alerts_agree_with_every_declared_budget() -> None:
    assert latency.run(Path()) == []


def test_a_one_second_search_breaches_and_a_one_second_generation_does_not() -> None:
    (search,) = latency.thresholds_for("search.run", _committed())
    (generation,) = latency.thresholds_for("generate_children.run", _committed())
    assert search < ONE_SECOND
    assert generation > ONE_SECOND


def test_one_threshold_for_every_operation_is_refused_where_it_is_wrong() -> None:
    found = latency.check(
        {"improve_story.run": 4000, "summarize.run": 8000}, _planted(_rule(".*", 8)), EDGES, "op"
    )
    assert [v.message for v in found] == ["op improve_story.run fires above 8.0 s; budget 4000 ms"]


def test_an_operation_no_rule_selects_and_one_two_rules_select_are_refused() -> None:
    rules = _planted(_rule("search[.].*", 0.8), _rule("(search|index)[.].*", 0.8))
    found = latency.check({"search.run": 800, "translate.run": 800}, rules, EDGES, "op")
    assert [v.message for v in found] == [
        "op search.run is judged by 2 rules",
        "op translate.run is judged by 0 rules",
    ]


def test_a_threshold_between_bucket_edges_is_refused() -> None:
    found = latency.check({"unfurl.run": 3000}, _planted(_rule("unfurl[.].*", 3)), EDGES, "op")
    assert "Planted fires above 3.0 s, not a bucket edge" in [v.message for v in found]


def test_a_negative_matcher_selects_what_it_does_not_name() -> None:
    (rule,) = _planted(_rule("x", 8))
    negative = latency.LatencyRule("N", "!~", "search[.].*", 8.0)
    assert not negative.selects("search.run")
    assert negative.selects("summarize.run")
    assert rule.selects("x")
