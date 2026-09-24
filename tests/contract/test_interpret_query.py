"""interpret_query.run through the app: a checked query, a refusal outside the grammar, the switch."""

import json
from datetime import datetime
from uuid import UUID

import httpx

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.interpret_query import InterpretQueryRequest, InterpretQueryResponse
from catalyst_ai.platform.auth import capability_of
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.interpret_query.conftest import GRAMMAR
from tools.origin import SigningAuth

INTERPRET = "/v1/interpret-query"
ORG = UUID("11111111-1111-7111-8111-111111111111")


def _body(text: str = "my open bugs") -> dict[str, object]:
    request = InterpretQueryRequest(
        organization_id=ORG,
        capability_version="1.0.0",
        text=text,
        grammar=GRAMMAR,
        now=datetime.fromisoformat("2026-09-24T01:30:00+03:00"),
    )
    return request.model_dump(mode="json")


def _answer(query: str) -> str:
    return json.dumps(
        {"query": query, "explanation": "Filter", "unresolved": [], "rationale": "Mapped."}
    )


def _client(texts: list[str], **overrides: object) -> httpx.AsyncClient:
    settings = make_settings(**overrides)
    runtime = make_runtime(ScriptedProvider(texts), settings)
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        auth=SigningAuth(capability_of(app), runtime.clock),
    )


async def test_interpret_query_run_returns_a_checked_query_and_refuses_one_outside() -> None:
    client = _client([_answer("status != done and issuetype = bug")])
    response = await client.post(INTERPRET, json=_body())
    assert response.status_code == 200, response.text
    answer = InterpretQueryResponse.model_validate(response.json())
    assert answer.query == 'issuetype = "Bug" AND status != "Done"'
    invented = _client([_answer("colour = red")])
    refused = await invented.post(INTERPRET, json=_body("red things"))
    error = refused.json()["error"]
    assert error["code"] == "ai.output.invalid"
    assert [detail["code"] for detail in error["details"]] == ["query_not_in_grammar"]
    off = _client([], capability_interpret_query=CapabilitySettings(enabled=False))
    disabled = await off.post(INTERPRET, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
