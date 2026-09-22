"""The registry: counters, gauges and histograms, and an exposition a collector can parse."""

from catalyst_ai.platform.observability import Metrics
from catalyst_ai.platform.observability.metrics import PREFIX, REQUESTS


def test_counters_gauges_and_totals() -> None:
    metrics = Metrics()
    metrics.count(REQUESTS, {"operation": "unfurl.run", "status": "2xx"})
    metrics.count(REQUESTS, {"operation": "unfurl.run", "status": "2xx"})
    metrics.count(REQUESTS, {"operation": "summarize.run", "status": "5xx"}, 3)
    metrics.set_gauge("jobs", 7, {"state": "queued"})
    assert metrics.value(REQUESTS, {"operation": "unfurl.run", "status": "2xx"}) == 2
    assert metrics.total(REQUESTS) == 5
    assert metrics.value("jobs", {"state": "queued"}) == 7
    assert metrics.value(REQUESTS, {"operation": "nobody", "status": "2xx"}) == 0
    assert metrics.total("nothing") == 0


def test_a_histogram_is_cumulative_and_carries_its_sum() -> None:
    metrics = Metrics(buckets=(0.1, 1.0))
    for seconds in (0.05, 0.5, 5.0):
        metrics.observe("duration", seconds, {"operation": "ask"})
    histogram = metrics.histogram("duration", {"operation": "ask"})
    assert histogram.counts == (1, 2, 3)
    assert histogram.count == 3
    assert histogram.total == 5.55
    assert metrics.histogram("duration", {"operation": "none"}).count == 0


def test_the_exposition_is_sorted_text_with_escaped_labels() -> None:
    metrics = Metrics(buckets=(1.0,))
    metrics.count("errors", {"code": 'ai."x"'})
    metrics.set_gauge("jobs", 2, {"state": "running"})
    metrics.observe("duration", 0.5)
    lines = metrics.render().splitlines()
    assert f'{PREFIX}errors_total{{code="ai.\\"x\\""}} 1' in lines
    assert f'{PREFIX}jobs{{state="running"}} 2' in lines
    assert f'{PREFIX}duration_bucket{{le="1"}} 1' in lines
    assert f'{PREFIX}duration_bucket{{le="+Inf"}} 1' in lines
    assert f"{PREFIX}duration_sum 0.5" in lines
    assert f"{PREFIX}duration_count 1" in lines
    assert metrics.render().endswith("\n")
