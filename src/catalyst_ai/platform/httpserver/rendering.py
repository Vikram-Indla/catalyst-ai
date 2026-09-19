"""The single place an error becomes a response and a request gains its id."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.ids import new_request_id

REQUEST_ID_HEADER = "X-Request-Id"
RETRY_AFTER_HEADER = "Retry-After"
MS_PER_SECOND = 1000
log = logging.getLogger(__name__)


def request_id_of(request: Request) -> str:
    """Return the id the middleware attached, or a fresh one when called before it."""
    attached = getattr(request.state, "request_id", None)
    return attached if isinstance(attached, str) else new_request_id()


def render_error(request: Request, error: Error) -> JSONResponse:
    """Render a catalog error as the envelope with the status and headers the code implies."""
    request_id = request_id_of(request)
    headers = {REQUEST_ID_HEADER: request_id}
    if error.retry_after_ms is not None:
        headers[RETRY_AFTER_HEADER] = str(max(1, error.retry_after_ms // MS_PER_SECOND))
    body = error.envelope(request_id).model_dump(mode="json", exclude_none=True)
    return JSONResponse(status_code=error.status, content=body, headers=headers)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a request id to every request and echo it on the response."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Mint or reuse the id, then continue."""
        request.state.request_id = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request.state.request_id
        return response


def _details_of(exc: RequestValidationError) -> list[ErrorDetail]:
    details: list[ErrorDetail] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", ()) if part != "body")
        details.append(
            ErrorDetail(field=location or "body", code=str(item.get("type")), message="invalid")
        )
    return details


def install_error_handlers(app: FastAPI) -> None:
    """Register the three handlers: catalog errors, validation failures, everything else."""

    @app.exception_handler(Error)
    async def _catalog(request: Request, exc: Error) -> JSONResponse:
        return render_error(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        error = Error(
            ErrorCode.VALIDATION_INVALID_INPUT, "the request is invalid", details=_details_of(exc)
        )
        return render_error(request, error)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error", extra={"request_id": request_id_of(request)})
        return render_error(request, Error(ErrorCode.INTERNAL_ERROR, "internal error"))
