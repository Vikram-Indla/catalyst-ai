"""Request ids, error rendering and the handlers the composition root installs."""

from catalyst_ai.platform.httpserver.document import with_error_responses, with_job_results
from catalyst_ai.platform.httpserver.rendering import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    install_error_handlers,
    render_error,
    request_id_of,
)
from catalyst_ai.platform.httpserver.sse import encode, stream_response

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdMiddleware",
    "encode",
    "install_error_handlers",
    "render_error",
    "request_id_of",
    "stream_response",
    "with_error_responses",
    "with_job_results",
]
