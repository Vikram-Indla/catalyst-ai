"""render_error: status, envelope, request id and Retry-After."""

from fastapi import Request

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.httpserver import REQUEST_ID_HEADER, render_error, request_id_of


def _request(request_id: str | None = None) -> Request:
    scope = {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""}
    request = Request(scope)
    if request_id is not None:
        request.state.request_id = request_id
    return request


def test_request_id_attached_or_minted() -> None:
    assert request_id_of(_request("abc")) == "abc"
    assert len(request_id_of(_request())) == 16


def test_render_error_sets_status_headers_and_body() -> None:
    error = Error(ErrorCode.BUDGET_EXCEEDED, "m", retry_after_ms=2500)
    response = render_error(_request("rid"), error)
    assert response.status_code == 429
    assert response.headers[REQUEST_ID_HEADER] == "rid"
    assert response.headers["Retry-After"] == "2"
    assert b'"request_id":"rid"' in response.body
    assert b"retry_after_ms" in response.body


def test_render_error_without_retry() -> None:
    response = render_error(_request("rid"), Error(ErrorCode.INPUT_REJECTED, "m"))
    assert "Retry-After" not in response.headers
    assert b"retry_after_ms" not in response.body
