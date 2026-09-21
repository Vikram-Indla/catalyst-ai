"""release_notes.run through the app: the fixture path, the record rules, every listed error."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.release_notes import ReleaseNotesResponse
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.recorded import RecordedTransport
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.release_notes.conftest import CHANGES, entry, notes_text
from tools import evalkit

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "release-notes"
ORG = "11111111-1111-7111-8111-111111111111"
PATH = "/v1/release-notes"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "notes",
        "release": {"name": "Board export", "version": "2.4.0"},
        "changes": CHANGES,
        "audience": "internal",
    }
    body.update(overrides)
    return body


def _client(runtime: RuntimeContext, settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        headers={"Authorization": "Bearer test-token"},
    )


def _scripted(texts: list[str], **overrides: object) -> tuple[httpx.AsyncClient, ScriptedProvider]:
    provider = ScriptedProvider(texts)
    settings = make_settings(service_tokens=[SecretStr("test-token")], **overrides)
    return _client(make_runtime(provider, settings), settings), provider


@pytest.fixture
async def recorded() -> AsyncIterator[httpx.AsyncClient]:
    settings = evalkit.inert_settings(cache_ttl_seconds=3600).model_copy(
        update={"service_tokens": [SecretStr("test-token")]}
    )
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES), settings)
    client = _client(runtime, settings)
    yield client
    await client.aclose()


async def test_release_notes_run_answers_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    cases = {
        c.id: c for c in evalkit.load_cases(REPO_ROOT / "evals" / "release-notes" / "set.jsonl")
    }
    response = await recorded.post(PATH, json=cases["notes-board-export-8"].input)
    assert response.status_code == 200, response.text
    body = ReleaseNotesResponse.model_validate(response.json())
    request_changes = cases["notes-board-export-8"].input["changes"]
    assert isinstance(request_changes, list)
    done = {c["id"] for c in request_changes if c["status_category"] == "done"}
    noted = {e.source_id for s in body.sections for e in s.entries}
    assert noted == done
    assert body.in_flight == [c["id"] for c in request_changes if c["id"] not in done]
    assert body.empty_reason is None


async def test_release_notes_run_refuses_an_invented_entry() -> None:
    sections = [{"kind": "story", "entries": [entry("chg-77", "Something nobody sent")]}]
    client, _ = _scripted([notes_text(sections=sections, highlights=[])])
    response = await client.post(PATH, json=_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.invalid"
    assert response.json()["error"]["details"][0]["code"] == "untraceable_entry"
    assert response.json()["error"]["details"][0]["message"] == "chg-77"


async def test_release_notes_run_switch_version_scanner_and_budget() -> None:
    off, provider = _scripted(
        [notes_text()], capability_release_notes=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(PATH, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([notes_text()])
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(
        PATH, json=_body(changes=[{**CHANGES[0], "title": "call 10.0.0.12 tonight"}])
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    big = await client.post(
        PATH,
        json=_body(
            changes=[{**CHANGES[0], "id": f"c{i}", "description": "y" * 4_000} for i in range(11)]
        ),
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.input.too_large"
    capped, _ = _scripted([notes_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(PATH, json=_body())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(PATH, json=_body())
    assert broken.json()["error"]["code"] == "ai.output.invalid"
    unsafe, _ = _scripted(
        [
            notes_text(
                sections=[
                    {"kind": "story", "entries": [entry("chg-1", "See https://evil.example/x")]}
                ],
                highlights=[],
            )
        ]
    )
    leaked = await unsafe.post(PATH, json=_body())
    assert leaked.json()["error"]["code"] == "ai.output.unsafe"


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (Fault(status=503), "ai.provider.unavailable"),
        (Fault(raises=httpx.ReadTimeout), "ai.provider.timeout"),
        (Fault(status=429), "ai.provider.quota"),
        (Fault(body={"candidates": [{"finishReason": "SAFETY"}]}), "ai.provider.rejected"),
    ],
    ids=["unavailable", "timeout", "quota", "rejected"],
)
async def test_release_notes_run_provider_failures(fault: Fault, code: str) -> None:
    settings = evalkit.inert_settings().model_copy(
        update={"service_tokens": [SecretStr("test-token")]}
    )
    base = evalkit.runtime_over(FaultTransport([fault]), settings)
    client_http = httpx.AsyncClient(transport=FaultTransport([fault]), timeout=1.0)
    provider = GeminiProvider(
        settings, client_http, base.clock, RetryPolicy(attempts=1, base_ms=0, max_ms=0, seed=1)
    )
    runtime = RuntimeContext(
        settings=settings,
        provider=provider,
        cache=base.cache,
        budgets=base.budgets,
        clock=base.clock,
        storage=base.storage,
    )
    client = _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.json()["error"]["code"] == code
