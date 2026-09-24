"""brief.run through the app: a cited briefing, a refusal of an unseen number, the switch."""

import httpx

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.brief import BriefResponse
from catalyst_ai.platform.auth import capability_of
from tests.unit.capabilities.brief.conftest import answer, brief_request
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools.origin import SigningAuth

BRIEF = "/v1/brief"


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


async def test_brief_run_returns_a_cited_briefing_and_refuses_an_unseen_number() -> None:
    body = brief_request().model_dump(mode="json")
    response = await _client([answer()]).post(BRIEF, json=body)
    assert response.status_code == 200, response.text
    briefing = BriefResponse.model_validate(response.json())
    assert all(sentence.cites for sentence in briefing.summary)
    lying = answer(summary=[{"text": "Done at 100%.", "cites": ["O-1"]}])
    refused = await _client([lying]).post(BRIEF, json=body)
    error = refused.json()["error"]
    assert error["code"] == "ai.output.invalid"
    assert [detail["code"] for detail in error["details"]] == ["unseen_number"]
    off = _client([], capability_brief=CapabilitySettings(enabled=False))
    disabled = await off.post(BRIEF, json=body)
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
