"""The three routes declare their capability, version and every error code they can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.routes import (
    ASK_ERROR_CODES,
    GENERATE_ERROR_CODES,
    INGEST_ERROR_CODES,
    router,
)


def test_routes_declare_their_contract() -> None:
    routes = {r.path: r for r in router.routes if isinstance(r, APIRoute)}
    expected = {
        "/v1/documents/ingest": ("documents.ingest", INGEST_ERROR_CODES),
        "/v1/documents/ask": ("documents.ask", ASK_ERROR_CODES),
        "/v1/documents/generate": ("documents.generate", GENERATE_ERROR_CODES),
    }
    for path, (operation_id, codes) in expected.items():
        route = routes[path]
        extra = route.openapi_extra or {}
        assert route.operation_id == operation_id
        assert extra["x-capability"] == descriptor.name
        assert set(extra["x-error-codes"]) == {c.value for c in codes}
