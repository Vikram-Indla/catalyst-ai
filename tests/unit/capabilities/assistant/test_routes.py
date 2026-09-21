"""The two routes declare their capability, version and every error code they can return."""

from fastapi.routing import APIRoute

from catalyst_ai.capabilities.assistant import descriptor
from catalyst_ai.capabilities.assistant.routes import ERROR_CODES, router


def test_routes_declare_their_contract() -> None:
    routes = {r.path: r for r in router.routes if isinstance(r, APIRoute)}
    expected = {
        "/v1/assistant/turn:stream": "assistant.turn",
        "/v1/assistant/turn": "assistant.turn_sync",
    }
    for path, operation_id in expected.items():
        route = routes[path]
        extra = route.openapi_extra or {}
        assert route.operation_id == operation_id
        assert extra["x-capability"] == descriptor.name
        assert set(extra["x-error-codes"]) == {c.value for c in ERROR_CODES}
    stream = routes["/v1/assistant/turn:stream"]
    assert "text/event-stream" in str(stream.responses[200]["content"])
