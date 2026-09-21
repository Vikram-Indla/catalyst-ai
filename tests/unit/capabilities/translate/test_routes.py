"""The route declares its capability, version and every error code it can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.routes import ERROR_CODES, router


def test_route_declares_its_contract() -> None:
    route = next(r for r in router.routes if isinstance(r, APIRoute) and r.path == "/v1/translate")
    extra = route.openapi_extra or {}
    assert route.operation_id == "translate.run"
    assert extra["x-capability"] == descriptor.name
    assert set(extra["x-error-codes"]) == {c.value for c in ERROR_CODES}
