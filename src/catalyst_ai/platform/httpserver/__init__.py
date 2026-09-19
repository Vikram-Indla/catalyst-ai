"""Request ids, error rendering and the handlers the composition root installs."""

from catalyst_ai.platform.httpserver.rendering import (
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    install_error_handlers,
    render_error,
    request_id_of,
)

__all__ = [
    "REQUEST_ID_HEADER",
    "RequestIdMiddleware",
    "install_error_handlers",
    "render_error",
    "request_id_of",
]
