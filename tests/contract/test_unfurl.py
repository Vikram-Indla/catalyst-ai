"""unfurl.run through the app: a card from supplied content; the door; no URL field."""

import httpx
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.unfurl import UnfurlResponse
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.unfurl.conftest import card_text, unfurl_request

UNFURL = "/v1/unfurl"


def _client(texts: list[str], **overrides: object) -> httpx.AsyncClient:
    settings = make_settings(service_tokens=[SecretStr("test-token")], **overrides)
    app = create_app(settings, make_runtime(ScriptedProvider(texts), settings))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        headers={"Authorization": "Bearer test-token"},
    )


async def test_unfurl_run_builds_a_card_and_refuses_at_the_door() -> None:
    client = _client([card_text()])
    response = await client.post(UNFURL, json=unfurl_request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    card = UnfurlResponse.model_validate(response.json())
    assert card.title == "Login button broken on mobile"
    assert [f.label for f in card.facts] == ["status", "since"]
    with_url = {**unfurl_request().model_dump(mode="json"), "url": "https://example.com/x"}
    refused = await client.post(UNFURL, json=with_url)
    assert refused.status_code == 400
    off = _client([card_text()], capability_unfurl=CapabilitySettings(enabled=False))
    disabled = await off.post(UNFURL, json=unfurl_request().model_dump(mode="json"))
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    broken = _client(["not json"])
    invalid = await broken.post(UNFURL, json=unfurl_request().model_dump(mode="json"))
    assert invalid.json()["error"]["code"] == "ai.output.invalid"
