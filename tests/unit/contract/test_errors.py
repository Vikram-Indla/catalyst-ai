"""The catalog: every code has a status; the envelope round-trips."""

from catalyst_ai.contract.errors import (
    HTTP_STATUS,
    PLATFORM_CODES,
    ErrorBody,
    ErrorCode,
    ErrorEnvelope,
)


def test_every_code_has_a_status() -> None:
    assert set(ErrorCode) == set(HTTP_STATUS)


def test_platform_codes_are_catalogued() -> None:
    assert set(ErrorCode) >= PLATFORM_CODES


def test_envelope_round_trips() -> None:
    envelope = ErrorEnvelope(
        error=ErrorBody(code=ErrorCode.INPUT_REJECTED, message="m"), request_id="r"
    )
    assert ErrorEnvelope.model_validate(envelope.model_dump()) == envelope
    assert envelope.error.details == []
    assert envelope.error.retry_after_ms is None
