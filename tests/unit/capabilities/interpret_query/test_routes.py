"""The route declares its capability, version and every error code it can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.interpret_query import descriptor
from catalyst_ai.capabilities.interpret_query.routes import ERROR_CODES, router
from catalyst_ai.contract.errors import ErrorCode


def test_route_declares_its_contract() -> None:
    route = next(r for r in router.routes if isinstance(r, APIRoute))
    extra = route.openapi_extra or {}
    assert route.path == "/v1/interpret-query"
    assert route.operation_id == "interpret_query.run"
    assert extra["x-capability"] == descriptor.name
    assert set(extra["x-error-codes"]) == {c.value for c in ERROR_CODES}
    assert ErrorCode.OUTPUT_INVALID in ERROR_CODES
