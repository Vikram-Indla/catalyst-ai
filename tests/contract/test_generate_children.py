"""generate_children.run through the app: the fixture path, every listed error code, tenancy, the switch."""

from collections.abc import AsyncIterator

import httpx
import pytest

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.generate_children import GenerateChildrenResponse
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.recorded import RecordedTransport
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.generate_children.conftest import (
    HIERARCHY,
    PARENT,
    candidates_text,
)
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import evalkit
from tools.origin import SigningAuth

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "generate-children"
ORG = "11111111-1111-7111-8111-111111111111"
OTHER = "22222222-2222-7222-8222-222222222222"
PATH = "/v1/generate-children"
EPIC = "Saved filter sharing"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "target": "stories",
        "hierarchy": ["theme", "initiative", "epic", "story", "task", "subtask"],
        "parent_level": "epic",
        "parent_title": EPIC,
        "parent_description": "Members share saved filters with a team. Shared filters carry view or edit permission. A shared filter appears in the team section. Changes by the owner propagate to everyone. Unsharing removes it from others.",
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


async def test_generate_children_run_returns_typed_candidates_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    response = await recorded.post(PATH, json=_body())
    assert response.status_code == 200, response.text
    proposal = GenerateChildrenResponse.model_validate(response.json())
    assert proposal.candidates
    assert all(c.type == "story" for c in proposal.candidates)
    assert all(c.acceptance_criteria for c in proposal.candidates if c.duplicate_of is None)
    assert proposal.empty_reason is None


async def test_generate_children_run_marks_a_supplied_sibling_as_duplicate(
    recorded: httpx.AsyncClient,
) -> None:
    sibling = "Members share saved filters with a team"
    response = await recorded.post(PATH, json=_body(siblings=[{"key": "PRJ-1", "title": sibling}]))
    assert response.status_code == 200, response.text
    proposal = GenerateChildrenResponse.model_validate(response.json())
    assert any(c.duplicate_of == sibling for c in proposal.candidates)
    assert all(c.duplicate_of != sibling or c.confidence <= 0.7 for c in proposal.candidates)


async def test_generate_children_run_second_organisation_never_sees_the_first_cache(
    recorded: httpx.AsyncClient,
) -> None:
    await recorded.post(PATH, json=_body())
    again = await recorded.post(PATH, json=_body())
    assert again.json()["usage"]["cache_hit"] is True
    other = await recorded.post(PATH, json=_body(organization_id=OTHER))
    assert other.status_code == 200
    assert other.json()["usage"]["cache_hit"] is False


async def test_generate_children_run_hierarchy_violation_in_the_request(
    recorded: httpx.AsyncClient,
) -> None:
    response = await recorded.post(PATH, json=_body(child_level="task"))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ai.input.rejected"
    assert response.json()["error"]["details"][0]["code"] == "hierarchy_violation"
    big = await recorded.post(
        PATH, json=_body(parent_description="x" * 20_000, source_texts=["y" * 20_000, "z" * 20_000])
    )
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.input.too_large"


async def test_generate_children_run_wrong_level_output_is_output_invalid() -> None:
    runtime, settings, _ = _scripted([candidates_text("a", level="task")])
    client = await _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.invalid"
    assert response.json()["error"]["details"][0]["code"] == "hierarchy_violation"
    runtime, settings, _ = _scripted([candidates_text("See OTHER-9")])
    client = await _client(runtime, settings)
    unsafe = await client.post(PATH, json=_body())
    assert unsafe.json()["error"]["code"] == "ai.output.unsafe"


async def test_generate_children_run_switch_version_and_budget() -> None:
    runtime, settings, provider = _scripted(
        [candidates_text("a")], capability_generate_children=CapabilitySettings(enabled=False)
    )
    client = await _client(runtime, settings)
    off = await client.post(PATH, json=_body())
    assert off.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    runtime, settings, _ = _scripted([candidates_text("a")], tenant_budget_default_micros_per_day=1)
    client = await _client(runtime, settings)
    capped = await client.post(PATH, json=_body())
    assert capped.json()["error"]["code"] == "ai.budget.exceeded"
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"


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
async def test_generate_children_run_provider_failures(fault: Fault, code: str) -> None:
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
    assert response.json()["error"]["code"] == code
    assert HIERARCHY[3] == "story"
    assert PARENT.startswith("Members")
