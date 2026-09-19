"""Every provider failure maps to a catalog code; the raw message never travels."""

import httpx

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.resilience import BreakerOpenError
from catalyst_ai.providers.gemini import errors


def test_status_mapping() -> None:
    assert errors.from_status(429, 0, "r").code is ErrorCode.PROVIDER_QUOTA
    assert errors.from_status(503, 0, "r").code is ErrorCode.PROVIDER_UNAVAILABLE
    assert errors.from_status(400, 0, "r").code is ErrorCode.PROVIDER_REJECTED


def test_transport_mapping() -> None:
    assert errors.from_transport(BreakerOpenError(1500), "r").retry_after_ms == 1500
    assert errors.from_transport(httpx.ReadTimeout("t"), "r").code is ErrorCode.PROVIDER_TIMEOUT
    assert (
        errors.from_transport(httpx.ConnectError("c"), "r").code is ErrorCode.PROVIDER_UNAVAILABLE
    )


def test_finish_reason_mapping() -> None:
    assert errors.from_finish_reason("SAFETY", "r") is not None
    assert errors.from_finish_reason("STOP", "r") is None
    assert errors.from_finish_reason(None, "r") is None


def test_retryable() -> None:
    request = httpx.Request("POST", "http://p/")
    assert errors.is_retryable(httpx.ReadTimeout("t"))
    assert errors.is_retryable(
        httpx.HTTPStatusError("s", request=request, response=httpx.Response(503, request=request))
    )
    assert not errors.is_retryable(
        httpx.HTTPStatusError("s", request=request, response=httpx.Response(400, request=request))
    )
    assert not errors.is_retryable(ValueError())
