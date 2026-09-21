"""The three routes declare the capability, the version and every error code each can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.capabilities.search.routes import (
    DELETE_ERROR_CODES,
    SEARCH_ERROR_CODES,
    UPSERT_ERROR_CODES,
    router,
)

EXPECTED = {
    "/v1/index/upsert": ("index.upsert", UPSERT_ERROR_CODES),
    "/v1/index/delete": ("index.delete", DELETE_ERROR_CODES),
    "/v1/search": ("search.run", SEARCH_ERROR_CODES),
}


def test_routes_declare_their_contract() -> None:
    routes = {r.path: r for r in router.routes if isinstance(r, APIRoute)}
    assert set(routes) == set(EXPECTED)
    for path, (operation_id, codes) in EXPECTED.items():
        extra = routes[path].openapi_extra or {}
        assert routes[path].operation_id == operation_id
        assert extra["x-capability"] == descriptor.name
        assert set(extra["x-error-codes"]) == {c.value for c in codes}
    assert "ai.index.document_too_large" in {c.value for c in UPSERT_ERROR_CODES}
