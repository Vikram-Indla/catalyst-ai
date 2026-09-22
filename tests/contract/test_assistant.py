"""assistant.* through the app: the stream's frames, a fault mid-stream, the whole form, budgets."""

import json
from typing import Any

import httpx

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.assistant import TurnResponse
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.assistant.conftest import (
    ITEM_REPLY,
    ROLLBACK_REPLY,
    completion,
    grounded_request,
    grounded_runtime,
    turn_request,
)
from tests.unit.capabilities.improve_story.conftest import (
    STREAM_FAULT,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools.origin import SigningAuth

STREAM = "/v1/assistant/turn:stream"
WHOLE = "/v1/assistant/turn"


def _client(runtime: RuntimeContext, settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        auth=SigningAuth(capability_of(app), runtime.clock),
    )


def _scripted(texts: list[str], **overrides: object) -> tuple[httpx.AsyncClient, ScriptedProvider]:
    provider = ScriptedProvider(texts)
    settings = make_settings(**overrides)
    return _client(make_runtime(provider, settings), settings), provider


def _events(body: str) -> list[tuple[str, dict[str, Any]]]:
    events = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        events.append((lines["event"], json.loads(lines["data"])))
    return events


async def test_assistant_turn_streams_deltas_citations_usage_and_done() -> None:
    settings = make_settings()
    runtime = await grounded_runtime([ROLLBACK_REPLY])
    client = _client(runtime, settings)
    async with client.stream("POST", STREAM, json=grounded_request().model_dump(mode="json")) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        body = (await r.aread()).decode()
    events = _events(body)
    kinds = [kind for kind, _ in events]
    assert kinds[0] == "delta"
    assert kinds[-1] == "done"
    assert kinds.count("usage") == 1
    assert "citation" in kinds
    prose = "".join(str(data["text"]) for kind, data in events if kind == "delta")
    result = TurnResponse.model_validate(events[-1][1]["result"])
    assert prose.rstrip() == result.reply
    assert "---" not in prose
    assert result.sources[0].citation is not None
    assert result.sources[0].citation.chunk_id == "kb-main/doc-runbook#1"


async def test_assistant_turn_fault_mid_stream_ends_with_an_error_frame() -> None:
    client, _ = _scripted([STREAM_FAULT])
    async with client.stream("POST", STREAM, json=turn_request().model_dump(mode="json")) as r:
        assert r.status_code == 200
        body = (await r.aread()).decode()
    events = _events(body)
    assert [kind for kind, _ in events] == ["error"]
    assert events[0][1]["error"]["error"]["code"] == "ai.provider.unavailable"
    uncited, _ = _scripted([completion("The button is broken on small screens for everyone.")])
    async with uncited.stream("POST", STREAM, json=turn_request().model_dump(mode="json")) as r:
        body = (await r.aread()).decode()
    events = _events(body)
    assert [kind for kind, _ in events][-1] == "error"
    assert events[-1][1]["error"]["error"]["details"][0]["code"] == "uncited_claim"
    assert any(kind == "delta" for kind, _ in events)


async def test_assistant_turn_sync_answers_and_the_door_refuses() -> None:
    client, provider = _scripted([ITEM_REPLY])
    response = await client.post(WHOLE, json=turn_request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    turn = TurnResponse.model_validate(response.json())
    assert [(s.marker, s.kind, s.source_id) for s in turn.sources] == [(1, "item", "item-41")]
    assert len(provider.calls) == 1
    bad = await client.post(WHOLE, json={**turn_request().model_dump(mode="json"), "history": []})
    assert bad.status_code == 400
    assistant_off, _ = _scripted(
        [ITEM_REPLY], capability_assistant=CapabilitySettings(enabled=False)
    )
    disabled = await assistant_off.post(WHOLE, json=turn_request().model_dump(mode="json"))
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    capped, _ = _scripted([ITEM_REPLY], tenant_budget_default_micros_per_day=1)
    async with capped.stream("POST", STREAM, json=turn_request().model_dump(mode="json")) as r:
        body = (await r.aread()).decode()
    assert _events(body)[-1][1]["error"]["error"]["code"] == "ai.budget.exceeded"
