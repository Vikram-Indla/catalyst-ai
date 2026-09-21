"""post_mortem.run through the app: the fixture path, the record rules, every listed error."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.post_mortem import PostMortemResponse
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
from tests.unit.capabilities.post_mortem.conftest import TIMELINE, draft_text, fact
from tools import evalkit

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "post-mortem"
ORG = "11111111-1111-7111-8111-111111111111"
PATH = "/v1/post-mortem"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "incident": {"key": "INC-9", "title": "Search cluster degraded", "severity": "sev2"},
        "timeline": TIMELINE,
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


async def test_post_mortem_run_answers_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    cases = {c.id: c for c in evalkit.load_cases(REPO_ROOT / "evals" / "post-mortem" / "set.jsonl")}
    response = await recorded.post(PATH, json=cases["search-6"].input)
    assert response.status_code == 200, response.text
    body = PostMortemResponse.model_validate(response.json())
    timeline = cases["search-6"].input["timeline"]
    assert isinstance(timeline, list)
    ids = [e["id"] for e in timeline]
    assert [f.source_id for f in body.facts] == ids
    assert all(set(f.evidence) <= set(ids) for f in body.contributing_factors)
    assert body.empty_reason is None


async def test_post_mortem_run_refuses_untraceable_facts_and_foreign_names() -> None:
    client, _ = _scripted([draft_text(facts=[fact("ev-99", "Invented")])])
    response = await client.post(PATH, json=_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.invalid"
    assert response.json()["error"]["details"][0]["code"] == "untraceable_entry"
    foreign, _ = _scripted([draft_text(summary="p7 caused it.")])
    unsafe = await foreign.post(PATH, json=_body())
    assert unsafe.json()["error"]["code"] == "ai.output.unsafe"
    assert unsafe.json()["error"]["details"][0]["code"] == "participant_not_in_thread"
    named = await client.post(
        PATH, json=_body(timeline=[{**TIMELINE[0], "participant": "Fatima Al-Sayed"}])
    )
    assert named.status_code == 400
    assert named.json()["error"]["code"] == "validation.invalid_input"


async def test_post_mortem_run_switch_version_scanner_and_budget() -> None:
    off, provider = _scripted(
        [draft_text()], capability_post_mortem=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(PATH, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([draft_text()])
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(
        PATH, json=_body(timeline=[{**TIMELINE[0], "text": "call 10.0.0.12 tonight"}])
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    big = await client.post(
        PATH,
        json=_body(
            timeline=[{**TIMELINE[0], "id": f"e{i}", "text": "y" * 4_000} for i in range(11)]
        ),
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.input.too_large"
    capped, _ = _scripted([draft_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(PATH, json=_body())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(PATH, json=_body())
    assert broken.json()["error"]["code"] == "ai.output.invalid"
    unsafe, _ = _scripted([draft_text(facts=[fact("ev-1", "See https://evil.example/x")])])
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
async def test_post_mortem_run_provider_failures(fault: Fault, code: str) -> None:
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
