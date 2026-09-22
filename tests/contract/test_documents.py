"""documents.* through the app: hostile files, the space, uncited answers, every listed error."""

from collections.abc import AsyncIterator

import httpx
import pytest

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.documents import AskResponse, DraftResponse, IngestResponse
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.recorded import RecordedTransport
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.documents.conftest import (
    answer_text,
    ask_request,
    bytes_request,
    draft_request,
    draft_text,
    ingest_request,
    sha,
)
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import evalkit
from tools.origin import SigningAuth

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "documents"
DOCUMENTS = REPO_ROOT / "tests" / "fixtures" / "documents"
INGEST = "/v1/documents/ingest"
ASK = "/v1/documents/ask"
GENERATE = "/v1/documents/generate"


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


@pytest.fixture
async def recorded() -> AsyncIterator[httpx.AsyncClient]:
    settings = evalkit.inert_settings(cache_ttl_seconds=3600)
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES), settings)
    await evalkit.ingest_corpus(runtime, REPO_ROOT / "evals" / "documents")
    client = _client(runtime, settings)
    yield client
    await client.aclose()


async def test_documents_ask_answers_from_the_recorded_fixture(recorded: httpx.AsyncClient) -> None:
    cases = {c.id: c for c in evalkit.load_cases(REPO_ROOT / "evals" / "documents" / "set.jsonl")}
    response = await recorded.post(ASK, json=cases["doc-runbook-3"].input)
    assert response.status_code == 200, response.text
    answer = AskResponse.model_validate(response.json())
    assert not answer.not_found
    assert "release manager" in answer.answer
    assert answer.answer.rstrip().endswith("[1]")
    assert answer.citations[0].document_id == "doc-runbook"
    trap = await recorded.post(ASK, json=cases["trap-6"].input)
    assert AskResponse.model_validate(trap.json()).not_found


async def test_documents_ingest_indexes_and_refuses_hostile_files() -> None:
    client, _ = _scripted([])
    response = await client.post(INGEST, json=ingest_request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    body = IngestResponse.model_validate(response.json())
    assert body.state == "indexed"
    assert body.chunks == 2
    for name, detail in (("bomb.docx", "document_too_large"), ("macro.docx", "document_malformed")):
        request = bytes_request((DOCUMENTS / "hostile" / name).read_bytes(), "docx")
        refused = await client.post(INGEST, json=request.model_dump(mode="json"))
        assert refused.status_code == 422
        assert refused.json()["error"]["code"] == "ai.input.rejected"
        assert refused.json()["error"]["details"][0]["code"] == detail
    restricted = "Mail someone@example.com"
    request = ingest_request(text=restricted, content_hash=sha(restricted))
    refused = await client.post(INGEST, json=request.model_dump(mode="json"))
    assert refused.json()["error"]["details"][0]["code"] == "document_restricted"
    assert "example.com" not in refused.text
    bad = await client.post(
        INGEST, json={**ingest_request().model_dump(mode="json"), "format": "xlsx"}
    )
    assert bad.status_code == 400


async def test_documents_ask_refuses_an_uncited_answer_and_stays_in_the_space() -> None:
    client, _ = _scripted([answer_text([{"text": "A guess.", "chunk_ids": []}])])
    await client.post(INGEST, json=ingest_request().model_dump(mode="json"))
    response = await client.post(ASK, json=ask_request().model_dump(mode="json"))
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai.output.invalid"
    assert response.json()["error"]["details"][0]["code"] == "uncited_claim"
    elsewhere = await client.post(ASK, json=ask_request(space_id="other").model_dump(mode="json"))
    assert AskResponse.model_validate(elsewhere.json()).not_found


async def test_documents_generate_traces_every_section() -> None:
    client, _ = _scripted([draft_text()])
    response = await client.post(GENERATE, json=draft_request().model_dump(mode="json"))
    assert response.status_code == 200, response.text
    draft = DraftResponse.model_validate(response.json())
    assert [s.sources for s in draft.sections] == [["src-runbook"], ["src-export"]]
    invented = [{"heading": "H", "text": "t", "sources": ["nope"]}]
    bad, _ = _scripted([draft_text(invented)])
    refused = await bad.post(GENERATE, json=draft_request().model_dump(mode="json"))
    assert refused.json()["error"]["details"][0]["code"] == "untraceable_entry"


async def test_documents_switch_version_scanner_and_budget() -> None:
    off, provider = _scripted(
        [answer_text()], capability_documents=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(ASK, json=ask_request().model_dump(mode="json"))
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([answer_text(), draft_text()])
    version = await client.post(
        ASK, json=ask_request(capability_version="2.0.0").model_dump(mode="json")
    )
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(
        ASK, json=ask_request(question="call 10.0.0.12").model_dump(mode="json")
    )
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    big = draft_request(sources=[{"id": f"s{i}", "text": "y" * 20_000} for i in range(3)])
    too_large = await client.post(GENERATE, json=big.model_dump(mode="json"))
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "ai.input.too_large"
    capped, _ = _scripted([draft_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(GENERATE, json=draft_request().model_dump(mode="json"))
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(GENERATE, json=draft_request().model_dump(mode="json"))
    assert broken.json()["error"]["code"] == "ai.output.invalid"
    leaking = [{"heading": "H", "text": "See https://evil.example/x", "sources": ["src-runbook"]}]
    unsafe, _ = _scripted([draft_text(leaking)])
    leaked = await unsafe.post(GENERATE, json=draft_request().model_dump(mode="json"))
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
async def test_documents_provider_failures(fault: Fault, code: str) -> None:
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
    client = _client(runtime, settings)
    response = await client.post(GENERATE, json=draft_request().model_dump(mode="json"))
    assert response.json()["error"]["code"] == code
    ingest = await client.post(INGEST, json=ingest_request().model_dump(mode="json"))
    assert ingest.json()["error"]["code"] in {
        code,
        "ai.provider.unavailable",
        "ai.index.unavailable",
    }
