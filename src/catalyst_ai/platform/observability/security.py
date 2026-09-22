"""Security events: one structured log line per refusal and a counter by reason, never content."""

import logging
from dataclasses import dataclass

from catalyst_ai.platform.observability.metrics import Metrics

log = logging.getLogger("catalyst_ai.security")
ORIGIN_REFUSED = "origin_refused"
JOB_QUARANTINED = "job_quarantined"


class SecurityCounters:
    """The security events' view of the process metrics: one counter per event and reason."""

    def __init__(self, metrics: Metrics | None = None) -> None:
        """Count into the process's metrics; a fresh registry when none is given (tests)."""
        self.metrics = metrics or Metrics()

    def count(self, event: str, reason: str) -> None:
        """Add one to the (event, reason) cell."""
        self.metrics.count(event, {"reason": reason})

    def value(self, event: str, reason: str | None = None) -> int:
        """Return one cell, or the sum over every reason of the event."""
        if reason is not None:
            return int(self.metrics.value(event, {"reason": reason}))
        return int(self.metrics.total(event))


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
