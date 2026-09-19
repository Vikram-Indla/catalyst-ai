"""The route declares its capability, version and every error code it can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.improve_story import descriptor
from catalyst_ai.capabilities.improve_story.routes import ERROR_CODES, router
from catalyst_ai.contract.errors import ErrorCode


def test_route_declares_its_contract() -> None:
    route = next(
        r for r in router.routes if isinstance(r, APIRoute) and r.path == "/v1/improve-story"
    )
    extra = route.openapi_extra or {}
    assert extra["x-capability"] == descriptor.name
    assert extra["x-capability-version"] == descriptor.version
    assert set(extra["x-error-codes"]) == {c.value for c in ERROR_CODES}
    assert ErrorCode.CAPABILITY_DISABLED in ERROR_CODES
