"""The one exception type a capability raises; the edge renders it as the envelope."""

from catalyst_ai.contract.errors import (
    HTTP_STATUS,
    ErrorBody,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
)


class Error(Exception):
    """A catalog error with its code, a developer-facing message and optional details."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: list[ErrorDetail] | None = None,
        retry_after_ms: int | None = None,
    ) -> None:
        """Build the error; the message must be stable and free of interpolated input."""
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []
        self.retry_after_ms = retry_after_ms

    @property
    def status(self) -> int:
        """Return the HTTP status the catalog assigns to the code."""
        return HTTP_STATUS[self.code]

    def envelope(self, request_id: str) -> ErrorEnvelope:
        """Render the error as the contract's envelope under the request id."""
        body = ErrorBody(
            code=self.code,
            message=self.message,
            details=self.details,
            retry_after_ms=self.retry_after_ms,
        )
        return ErrorEnvelope(error=body, request_id=request_id)
