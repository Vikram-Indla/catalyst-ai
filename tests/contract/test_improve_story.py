"""improve_story.run through the app: the happy path, every listed error code, tenancy, the switch."""

from collections.abc import AsyncIterator
from uuid import UUID

import httpx
import pytest

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.errors import ErrorCode, ErrorEnvelope
from catalyst_ai.contract.improve_story import ImproveStoryResponse
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.recorded import RecordedTransport
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import evalkit
from tools.origin import SigningAuth, unsigned

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "improve-story"
ORG = "11111111-1111-7111-8111-111111111111"
OTHER = "22222222-2222-7222-8222-222222222222"
PATH = "/v1/improve-story"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.1.0",
        "mode": "clarify",
        "item_type": "Story",
        "title": "Login with SSO",
        "description": "user should be able to login with the company SSO so they dont need password, this must work on mobile to and the session should stays for 8 hours",
    }
    body.update(overrides)
    return body


async def _client(runtime: RuntimeContext, settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        auth=SigningAuth(capability_of(app), runtime.clock),
    )


@pytest.fixture
async def recorded() -> AsyncIterator[httpx.AsyncClient]:
    settings = evalkit.inert_settings(cache_ttl_seconds=3600)
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES), settings)
    client = await _client(runtime, settings)
    yield client
    await client.aclose()


def _scripted(
    texts: list[str], **settings_overrides: object
) -> tuple[RuntimeContext, Settings, ScriptedProvider]:
    provider = ScriptedProvider(texts)
    settings = make_settings(**settings_overrides)
    return make_runtime(provider, settings), settings, provider


async def test_improve_story_run_returns_a_schema_valid_proposal_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    response = await recorded.post(PATH, json=_body())
    assert response.status_code == 200, response.text
    proposal = ImproveStoryResponse.model_validate(response.json())
    assert proposal.changed is True
    assert "8 hours" in proposal.improved_description
    assert proposal.capability_version == "1.2.0"
    assert proposal.usage.cost_micros > 0


async def test_improve_story_run_second_organisation_never_sees_the_first_cache(
    recorded: httpx.AsyncClient,
) -> None:
    first = await recorded.post(PATH, json=_body())
    again = await recorded.post(PATH, json=_body())
    assert again.json()["usage"]["cache_hit"] is True
    other = await recorded.post(PATH, json=_body(organization_id=OTHER))
    assert other.status_code == 200
    assert other.json()["usage"]["cache_hit"] is False
    assert first.json()["request_id"] != other.json()["request_id"]


async def test_improve_story_run_requires_proof_of_origin(recorded: httpx.AsyncClient) -> None:
    response = await recorded.post(PATH, json=_body(), auth=unsigned)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.origin.invalid"


async def test_improve_story_run_validation_invalid_input(recorded: httpx.AsyncClient) -> None:
    response = await recorded.post(PATH, json=_body(mode="rewrite"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation.invalid_input"


async def test_improve_story_run_contract_version_mismatch(recorded: httpx.AsyncClient) -> None:
    response = await recorded.post(PATH, json=_body(capability_version="2.0.0"))
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "ai.contract.version_mismatch"


async def test_improve_story_run_input_rejected_and_too_large(recorded: httpx.AsyncClient) -> None:
    rejected = await recorded.post(PATH, json=_body(description="mail someone@example.com"))
    assert rejected.status_code == 422
    envelope = ErrorEnvelope.model_validate(rejected.json())
    assert envelope.error.code is ErrorCode.INPUT_REJECTED
    assert envelope.error.code.value == "ai.input.rejected"
    assert "example.com" not in rejected.text
    big = await recorded.post(
        PATH,
        json=_body(
            description="x" * 20_000,
            parent_description="y" * 20_000,
            acceptance_criteria="z" * 10_000,
            focus_hint="h" * 500,
            title="t" * 500,
        ),
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.input.too_large"


async def test_improve_story_run_capability_disabled_without_a_call() -> None:
    runtime, settings, provider = _scripted(
        [GOOD_TEXT], capability_improve_story=CapabilitySettings(enabled=False)
    )
    client = await _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []


async def test_improve_story_run_budget_exceeded() -> None:
    runtime, settings, _ = _scripted([GOOD_TEXT], tenant_budget_default_micros_per_day=1)
    client = await _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "ai.budget.exceeded"
    assert "Retry-After" in response.headers


async def test_improve_story_run_output_invalid_and_unsafe() -> None:
    runtime, settings, _ = _scripted(["not json"])
    client = await _client(runtime, settings)
    invalid = await client.post(PATH, json=_body())
    assert invalid.status_code == 502
    assert invalid.json()["error"]["code"] == "ai.output.invalid"
    runtime, settings, _ = _scripted(
        [
            '{"description": "see OTHER-9", "acceptance_criteria": null, "rationale": "r", "changed": true}'
        ]
    )
    client = await _client(runtime, settings)
    unsafe = await client.post(PATH, json=_body())
    assert unsafe.status_code == 502
    assert unsafe.json()["error"]["code"] == "ai.output.unsafe"


@pytest.mark.parametrize(
    ("fault", "status", "code"),
    [
        (Fault(status=503), 503, "ai.provider.unavailable"),
        (Fault(raises=httpx.ReadTimeout), 504, "ai.provider.timeout"),
        (Fault(status=429), 429, "ai.provider.quota"),
        (Fault(body={"candidates": [{"finishReason": "SAFETY"}]}), 422, "ai.provider.rejected"),
    ],
    ids=["unavailable", "timeout", "quota", "rejected"],
)
async def test_improve_story_run_provider_failures(fault: Fault, status: int, code: str) -> None:
    settings = evalkit.inert_settings()
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
    client = await _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.status_code == status
    assert response.json()["error"]["code"] == code
    assert "injected" not in response.text


def test_fixtures_carry_a_manifest_naming_their_source() -> None:
    manifest = (FIXTURES / "_manifest.json").read_text(encoding="utf-8")
    assert "authored stand-in" in manifest or '"source": "live"' in manifest
    assert UUID(ORG).version == 7
