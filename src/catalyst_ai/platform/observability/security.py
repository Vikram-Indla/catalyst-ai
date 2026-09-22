"""Security events: one structured log line per refusal and a counter by reason, never content."""

import logging
from collections import Counter
from dataclasses import dataclass

log = logging.getLogger("catalyst_ai.security")
ORIGIN_REFUSED = "origin_refused"
JOB_QUARANTINED = "job_quarantined"


class SecurityCounters:
    """Counters the metrics endpoint reads, held by the app, keyed by event and reason."""

    def __init__(self) -> None:
        """Start at zero."""
        self._counts: Counter[tuple[str, str]] = Counter()

    def count(self, event: str, reason: str) -> None:
        """Add one to the (event, reason) cell."""
        self._counts[(event, reason)] += 1

    def value(self, event: str, reason: str | None = None) -> int:
        """Return one cell, or the sum over every reason of the event."""
        if reason is not None:
            return self._counts[(event, reason)]
        return sum(count for (name, _), count in self._counts.items() if name == event)


@dataclass(frozen=True)
class Where:
    """The ids an event is logged with; never a body, a claim's text or a key."""

    request_id: str
    capability: str | None = None
    key_id: str | None = None


def security_event(counters: SecurityCounters, event: str, reason: str, where: Where) -> None:
    """Log the event with its reason and count it."""
    counters.count(event, reason)
    log.warning(
        event,
        extra={
            "security_event": event,
            "reason": reason,
            "request_id": where.request_id,
            "capability": where.capability,
            "key_id": where.key_id,
        },
    )
