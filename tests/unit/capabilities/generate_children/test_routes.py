"""The route declares its capability, version and every error code it can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.generate_children import descriptor
from catalyst_ai.capabilities.generate_children.routes import ERROR_CODES, router


def test_route_declares_its_contract() -> None:
    route = next(
        r for r in router.routes if isinstance(r, APIRoute) and r.path == "/v1/generate-children"
    )
    extra = route.openapi_extra or {}
    assert extra["x-capability"] == descriptor.name
    assert set(extra["x-error-codes"]) == {c.value for c in ERROR_CODES}
