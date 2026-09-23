"""The metrics the ops port exposes: counters and histograms, labelled by ids, never by content.

One registry per process — the ops port renders it and every part of the process counts into
it — in the Prometheus text exposition format on the
the format every collector scrapes, so the collector stays the only exporter
(`ARCH-010 §2`). A label value is a capability, a model, an outcome, a reason or an
organisation id; a prompt, a completion or any member's text never reaches this module.
The bucket bounds carry an edge at every latency budget a capability declares (0.8 s for
retrieval, 4 to 15 s for the rest; `tools/checks/latency` holds the alerts to them), because a
quantile interpolated across the threshold it is judged by measures nothing.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from threading import Lock

PREFIX = "catalyst_ai_"
BUCKETS_S = (0.05, 0.1, 0.25, 0.5, 0.8, 1.0, 2.5, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 30.0, 60.0)
REQUESTS = "http_requests"
REQUEST_SECONDS = "http_request_duration_seconds"
PROVIDER_CALLS = "provider_calls"
PROVIDER_TOKENS = "provider_tokens"
PROVIDER_COST_MICROS = "provider_cost_micros"
PROVIDER_SECONDS = "provider_call_duration_seconds"
CACHE_LOOKUPS = "cache_lookups"
ERRORS = "errors"
BUDGET_REFUSED = "budget_refused"
BREAKER_OPEN = "provider_breaker_open"
JOBS = "jobs"
JOB_SECONDS = "job_duration_seconds"
ORIGIN_REFUSED = "origin_refused"
JOB_QUARANTINED = "job_quarantined"
Labels = Mapping[str, str]


def _key(name: str, labels: Labels | None) -> tuple[str, tuple[tuple[str, str], ...]]:
    return name, tuple(sorted((labels or {}).items()))


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _render_labels(labels: tuple[tuple[str, str], ...], extra: str = "") -> str:
    pairs = [f'{name}="{_escape(value)}"' for name, value in labels]
    if extra:
        pairs.append(extra)
    return "{" + ",".join(pairs) + "}" if pairs else ""


@dataclass(frozen=True)
class Histogram:
    """One histogram's state: the cumulative buckets, the sum and the count."""

    buckets: tuple[float, ...]
    counts: tuple[int, ...]
    total: float

    def observed(self, value: float) -> "Histogram":
        """Return the histogram with one more observation in it."""
        counts = tuple(
            count + (1 if value <= bound else 0)
            for count, bound in zip(self.counts, self.buckets, strict=True)
        )
        return Histogram(self.buckets, counts, self.total + value)

    @property
    def count(self) -> int:
        """How many observations; the last bucket is `+Inf` and holds them all."""
        return self.counts[-1]


def _empty(buckets: tuple[float, ...]) -> Histogram:
    return Histogram(buckets, tuple(0 for _ in buckets), 0.0)


class Metrics:
    """Counters, gauges and histograms for one process; `render` is what the collector scrapes."""

    def __init__(self, buckets: tuple[float, ...] = BUCKETS_S) -> None:
        """Start empty with the given histogram bounds (`+Inf` is added)."""
        self._buckets = (*buckets, float("inf"))
        self._counters: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._gauges: dict[tuple[str, tuple[tuple[str, str], ...]], float] = {}
        self._histograms: dict[tuple[str, tuple[tuple[str, str], ...]], Histogram] = {}
        self._lock = Lock()

    def count(self, name: str, labels: Labels | None = None, value: float = 1.0) -> None:
        """Add to a counter; counters only ever grow."""
        key = _key(name, labels)
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: Labels | None = None) -> None:
        """Set a gauge to a value read at this moment."""
        with self._lock:
            self._gauges[_key(name, labels)] = value

    def drop_gauge(self, name: str, labels: Labels | None = None) -> None:
        """Forget a gauge: a value nobody can read now is not a measurement (F-030's family)."""
        with self._lock:
            self._gauges.pop(_key(name, labels), None)

    def observe(self, name: str, value: float, labels: Labels | None = None) -> None:
        """Record one observation in a histogram, in seconds."""
        with self._lock:
            current = self._histograms.get(_key(name, labels)) or _empty(self._buckets)
            self._histograms[_key(name, labels)] = current.observed(value)

    def value(self, name: str, labels: Labels | None = None) -> float:
        """Read one counter or gauge; zero when nothing has been recorded, and nothing created."""
        key = _key(name, labels)
        with self._lock:
            return self._gauges.get(key, self._counters.get(key, 0.0))

    def total(self, name: str) -> float:
        """Sum a counter over every label set it carries."""
        with self._lock:
            return sum(value for (metric, _), value in self._counters.items() if metric == name)

    def histogram(self, name: str, labels: Labels | None = None) -> Histogram:
        """Read one histogram; an empty one when nothing has been observed."""
        with self._lock:
            return self._histograms.get(_key(name, labels)) or _empty(self._buckets)

    def render(self) -> str:
        """Return the exposition text: counters, then gauges, then histograms, sorted."""
        with self._lock:
            lines = [*self._counter_lines(), *self._gauge_lines(), *self._histogram_lines()]
        return "\n".join(lines) + "\n"

    def _counter_lines(self) -> Iterable[str]:
        for (name, labels), value in sorted(self._counters.items()):
            yield f"{PREFIX}{name}_total{_render_labels(labels)} {value:g}"

    def _gauge_lines(self) -> Iterable[str]:
        for (name, labels), value in sorted(self._gauges.items()):
            yield f"{PREFIX}{name}{_render_labels(labels)} {value:g}"

    def _histogram_lines(self) -> Iterable[str]:
        for (name, labels), histogram in sorted(self._histograms.items()):
            for bound, count in zip(histogram.buckets, histogram.counts, strict=True):
                edge = "+Inf" if bound == float("inf") else f"{bound:g}"
                yield f"{PREFIX}{name}_bucket{_render_labels(labels, f'le="{edge}"')} {count}"
            yield f"{PREFIX}{name}_sum{_render_labels(labels)} {histogram.total:g}"
            yield f"{PREFIX}{name}_count{_render_labels(labels)} {histogram.count}"
