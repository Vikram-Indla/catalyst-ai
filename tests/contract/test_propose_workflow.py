"""propose_workflow.run through the app: the fixture path, the structural refusal, every error."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.propose_workflow import ProposeWorkflowResponse
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
from tests.unit.capabilities.propose_workflow.conftest import (
    DESCRIPTION,
    GUARDS,
    STATUSES,
    TRANSITIONS,
    proposal_text,
    status,
    transition,
)
from tools import evalkit

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "propose-workflow"
ORG = "11111111-1111-7111-8111-111111111111"
PATH = "/v1/propose-workflow"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "description": DESCRIPTION,
        "item_type": "defect",
        "guard_vocabulary": GUARDS,
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


async def test_propose_workflow_run_returns_a_scheme_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    cases = evalkit.load_cases(REPO_ROOT / "evals" / "propose-workflow" / "set.jsonl")
    body = next(case for case in cases if case.id == "defect-guards").input
    response = await recorded.post(PATH, json=body)
    assert response.status_code == 200, response.text
    proposal = ProposeWorkflowResponse.model_validate(response.json())
    assert proposal.empty_reason is None
    assert [s.key for s in proposal.statuses if s.initial] == ["reported"]
    assert {s.key for s in proposal.statuses if s.terminal} == {"closed", "cancelled"}
    assert {g for t in proposal.transitions for g in t.guards} == {
        "assignee_set",
        "fix_version_set",
    }
    assert all(t.reason_code for t in proposal.transitions if t.kind.value == "reopen")


async def test_propose_workflow_run_refuses_a_scheme_the_engine_could_not_take() -> None:
    statuses = [*STATUSES, status("parked", "todo", order=6)]
    transitions = [*TRANSITIONS, transition("closed", "triaged", "backward")]
    client, _ = _scripted([proposal_text(statuses, transitions)])
    response = await client.post(PATH, json=_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.invalid"
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert codes == {"workflow_unreachable_status", "workflow_reason_missing"}


async def test_propose_workflow_run_yields_the_reason_for_a_vague_description() -> None:
    client, _ = _scripted([proposal_text([], [], "description_too_vague")])
    response = await client.post(PATH, json=_body(description="make it better"))
    assert response.status_code == 200, response.text
    proposal = ProposeWorkflowResponse.model_validate(response.json())
    assert proposal.empty_reason == "description_too_vague"
    assert proposal.statuses == []


async def test_propose_workflow_run_switch_version_scanner_and_budget() -> None:
    off, provider = _scripted(
        [proposal_text()], capability_propose_workflow=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(PATH, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([proposal_text()])
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(PATH, json=_body(description="ping 10.0.0.12 after triage"))
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    shape = await client.post(PATH, json=_body(allowed_categories=["todo"]))
    assert shape.status_code == 400
    assert shape.json()["error"]["code"] == "validation.invalid_input"
    capped, _ = _scripted([proposal_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(PATH, json=_body())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(PATH, json=_body())
    assert broken.json()["error"]["code"] == "ai.output.invalid"
    leaking = [{**STATUSES[0], "name": "See https://evil.example/x"}, *STATUSES[1:]]
    unsafe, _ = _scripted([proposal_text(leaking)])
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
async def test_propose_workflow_run_provider_failures(fault: Fault, code: str) -> None:
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
