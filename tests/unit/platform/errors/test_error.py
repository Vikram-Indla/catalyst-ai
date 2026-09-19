"""Error: status from the catalog; envelope rendering with details and retry."""

from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error


def test_status_follows_the_code() -> None:
    assert Error(ErrorCode.BUDGET_EXCEEDED, "m").status == 429


def test_envelope_carries_details_and_retry() -> None:
    error = Error(
        ErrorCode.INPUT_REJECTED,
        "m",
        details=[ErrorDetail(field="f", code="c", message="x")],
        retry_after_ms=1500,
    )
    envelope = error.envelope("rid")
    assert envelope.request_id == "rid"
    assert envelope.error.details[0].field == "f"
    assert envelope.error.retry_after_ms == 1500
    assert str(error) == "m"
