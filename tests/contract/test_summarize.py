"""summarize.run through the app: the fixture path, the participant rule, every listed error."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.summarize import SummarizeResponse
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
from tests.unit.capabilities.summarize.conftest import THREAD, summary_text
from tools import evalkit

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "summarize"
ORG = "11111111-1111-7111-8111-111111111111"
PATH = "/v1/summarize"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "comments",
        "items": THREAD,
        "item_title": "Export the board to CSV",
        "item_type": "Story",
        "target_words": 120,
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


async def test_summarize_run_returns_a_summary_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    body = evalkit.load_cases(REPO_ROOT / "evals" / "summarize" / "set.jsonl")[0].input
    response = await recorded.post(PATH, json=body)
    assert response.status_code == 200, response.text
    summary = SummarizeResponse.model_validate(response.json())
    assert summary.summary
    items = body["items"]
    assert isinstance(items, list)
    assert summary.covered_range.count == len(items)
    assert set(summary.participants_mentioned) <= {"p1", "p2", "p3", "p4"}


async def test_summarize_run_refuses_a_summary_naming_someone_outside_the_thread() -> None:
    client, _ = _scripted([summary_text("p1 and p9 agreed.", ("p1", "p9"))])
    response = await client.post(PATH, json=_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.unsafe"
    assert response.json()["error"]["details"][0]["code"] == "participant_not_in_thread"


async def test_summarize_run_caps_the_length_and_reports_the_range() -> None:
    long = "p1 said " + "word " * 400
    client, _ = _scripted([summary_text(long, ("p1",))])
    response = await client.post(PATH, json=_body(target_words=40))
    assert response.status_code == 200, response.text
    summary = SummarizeResponse.model_validate(response.json())
    assert len(summary.summary.split()) <= 61
    assert summary.covered_range.first_id == "c1"
    assert summary.covered_range.last_id == "c4"
    assert summary.confidence < 1.0


async def test_summarize_run_switch_version_scanner_and_budget() -> None:
    off, provider = _scripted(
        [summary_text()], capability_summarize=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(PATH, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([summary_text()])
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(
        PATH, json=_body(items=[{**THREAD[0], "text": "call 10.0.0.12 tonight"}])
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    big = await client.post(
        PATH,
        json=_body(items=[{**THREAD[0], "id": f"c{i}", "text": "y" * 4_000} for i in range(11)]),
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.input.too_large"
    capped, _ = _scripted([summary_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(PATH, json=_body())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(PATH, json=_body())
    assert broken.json()["error"]["code"] == "ai.output.invalid"


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
async def test_summarize_run_provider_failures(fault: Fault, code: str) -> None:
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
