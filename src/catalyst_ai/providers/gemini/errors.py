"""Provider failures become catalog errors here; the raw message goes to the log, never onward."""

import logging

import httpx

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.resilience import BreakerOpenError

HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR = 500
DEFAULT_RETRY_AFTER_MS = 5_000
BLOCKED_FINISH_REASONS = frozenset({"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII"})
log = logging.getLogger(__name__)


def from_status(status: int, body_excerpt_length: int, request_id: str) -> Error:
    """Map an HTTP failure to the catalog; the body's length is logged, never its text."""
    log.warning(
        "provider http failure",
        extra={"request_id": request_id, "status": status, "body_length": body_excerpt_length},
    )
    if status == HTTP_TOO_MANY_REQUESTS:
        return Error(
            ErrorCode.PROVIDER_QUOTA,
            "the provider rate-limited the call",
            retry_after_ms=DEFAULT_RETRY_AFTER_MS,
        )
    if status >= HTTP_SERVER_ERROR:
        return Error(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "the provider is unavailable",
            retry_after_ms=DEFAULT_RETRY_AFTER_MS,
        )
    return Error(ErrorCode.PROVIDER_REJECTED, "the provider rejected the call")


def from_transport(error: Exception, request_id: str) -> Error:
    """Map a transport-level failure (timeout, connection, open breaker) to the catalog."""
    if isinstance(error, BreakerOpenError):
        return Error(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "the provider circuit is open",
            retry_after_ms=error.retry_after_ms,
        )
    if isinstance(error, httpx.TimeoutException):
        log.warning("provider timeout", extra={"request_id": request_id})
        return Error(
            ErrorCode.PROVIDER_TIMEOUT,
            "the provider did not answer in time",
            retry_after_ms=DEFAULT_RETRY_AFTER_MS,
        )
    log.warning(
        "provider transport failure", extra={"request_id": request_id, "kind": type(error).__name__}
    )
    return Error(
        ErrorCode.PROVIDER_UNAVAILABLE,
        "the provider could not be reached",
        retry_after_ms=DEFAULT_RETRY_AFTER_MS,
    )


def from_finish_reason(reason: str | None, request_id: str) -> Error | None:
    """Map a blocked finish to a rejection; a normal finish maps to None."""
    if reason in BLOCKED_FINISH_REASONS:
        log.warning(
            "provider blocked the completion", extra={"request_id": request_id, "reason": reason}
        )
        return Error(ErrorCode.PROVIDER_REJECTED, "the provider blocked the completion")
    return None


def is_retryable(error: Exception) -> bool:
    """Only transient failures are retried: timeouts, connection errors, 5xx."""
    if isinstance(error, httpx.TimeoutException | httpx.ConnectError | httpx.RemoteProtocolError):
        return True
    return (
        isinstance(error, httpx.HTTPStatusError) and error.response.status_code >= HTTP_SERVER_ERROR
    )
