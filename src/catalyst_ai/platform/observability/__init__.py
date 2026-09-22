"""Every provider call is a content-free row; every refusal a security event with a reason."""

from catalyst_ai.platform.observability.calls import ProviderCallRow, log_provider_call
from catalyst_ai.platform.observability.metrics import Histogram, Metrics
from catalyst_ai.platform.observability.provider import MeteredProvider
from catalyst_ai.platform.observability.requests import RequestMetricsMiddleware
from catalyst_ai.platform.observability.scrape import router as metrics_router
from catalyst_ai.platform.observability.security import (
    JOB_QUARANTINED,
    ORIGIN_REFUSED,
    SecurityCounters,
    Where,
    security_event,
)

__all__ = [
    "JOB_QUARANTINED",
    "ORIGIN_REFUSED",
    "Histogram",
    "MeteredProvider",
    "Metrics",
    "ProviderCallRow",
    "RequestMetricsMiddleware",
    "SecurityCounters",
    "Where",
    "log_provider_call",
    "metrics_router",
    "security_event",
]
