"""index.upsert, index.delete and search.run through the app: shapes, every listed error, tenancy."""

import httpx
import pytest

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.search import IndexUpsertResult, SearchResponse
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from tests.unit.capabilities.improve_story.conftest import (
    FrozenClock,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.search.conftest import content_hash
from tools import evalkit
from tools.origin import SigningAuth

ORG = "11111111-1111-7111-8111-111111111111"
OTHER = "22222222-2222-7222-8222-222222222222"
UPSERT = "/v1/index/upsert"
DELETE = "/v1/index/delete"
SEARCH = "/v1/search"
LOGIN = "The login button is broken on mobile"
EXPORT = "Export the board to CSV with every column"


def _document(external_id: str, text: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "external_id": external_id,
        "kind": "story",
        "title": None,
        "text": text,
        "data_class": "CONFIDENTIAL",
        "content_hash": content_hash(None, text),
    }
    values.update(overrides)
    return values


def _upsert(*documents: dict[str, object], **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "corpus": "work_items",
        "documents": list(documents) or [_document("A-1", LOGIN), _document("A-2", EXPORT)],
    }
    body.update(overrides)
    return body


def _search(text: str = LOGIN, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "corpus": "work_items",
        "mode": "similar",
        "text": text,
    }
    body.update(overrides)
    return body


def _delete(*external_ids: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "corpus": "work_items",
        "external_ids": list(external_ids) or ["A-1"],
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
        auth=SigningAuth(capability_of(app), runtime.clock),
    )


def _scripted(**settings_overrides: object) -> tuple[httpx.AsyncClient, ScriptedProvider]:
    provider = ScriptedProvider(["{}"])
    settings = make_settings(**settings_overrides)
    return _client(make_runtime(provider, settings), settings), provider


async def test_index_upsert_indexes_and_reports_unchanged_on_repeat() -> None:
    client, provider = _scripted()
    first = await client.post(UPSERT, json=_upsert())
    assert first.status_code == 200, first.text
    indexed = IndexUpsertResult.model_validate(first.json())
    assert [r.unchanged for r in indexed.results] == [False, False]
    assert indexed.index_chunks == 2
    assert indexed.results[0].embedding_version == "d768-r1"
    second = await client.post(UPSERT, json=_upsert())
    assert [r["unchanged"] for r in second.json()["results"]] == [True, True]
    assert second.json()["usage"]["cost_micros"] == 0
    assert len(provider.embed_calls) == 1


async def test_index_upsert_refuses_an_oversized_document_and_a_full_index() -> None:
    client, _ = _scripted()
    big = await client.post(UPSERT, json=_upsert(_document("big", "x" * 20_001)))
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "ai.index.document_too_large"
    huge = await client.post(
        UPSERT, json=_upsert(*[_document(f"h{i}", "y" * 20_000) for i in range(3)])
    )
    assert huge.status_code == 413
    assert huge.json()["error"]["code"] == "ai.input.too_large"
    small, _ = _scripted(retrieval_index_max_chunks_per_organization=1)
    full = await small.post(UPSERT, json=_upsert())
    assert full.status_code == 429
    assert full.json()["error"]["code"] == "ai.budget.exceeded"
    assert full.json()["error"]["details"][0]["code"] == "index_budget"


async def test_index_upsert_refuses_the_scanner_the_version_and_the_switch() -> None:
    client, provider = _scripted()
    scanned = await client.post(UPSERT, json=_upsert(_document("A-1", "call 10.0.0.12")))
    assert scanned.status_code == 422
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    version = await client.post(UPSERT, json=_upsert(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    assert provider.embed_calls == []
    off, _ = _scripted(capability_search=CapabilitySettings(enabled=False))
    disabled = await off.post(UPSERT, json=_upsert())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"


async def test_index_delete_forgets_keys_and_reports_chunks() -> None:
    client, _ = _scripted()
    await client.post(UPSERT, json=_upsert())
    deleted = await client.post(DELETE, json=_delete("A-1", "missing"))
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_chunks"] == 1
    again = await client.post(DELETE, json=_delete("A-1"))
    assert again.json()["deleted_chunks"] == 0


async def test_search_run_returns_ranked_hits_with_provenance() -> None:
    client, _ = _scripted()
    await client.post(UPSERT, json=_upsert())
    response = await client.post(SEARCH, json=_search(exclude_external_ids=["A-2"]))
    assert response.status_code == 200, response.text
    found = SearchResponse.model_validate(response.json())
    assert [h.external_id for h in found.hits] == ["A-1"]
    assert found.hits[0].provenance.vector_rank == 1
    assert found.hits[0].snippet.startswith("The login")
    assert found.fusion.startswith("rrf")
    query = await client.post(SEARCH, json=_search("csv export", mode="query", k=1))
    assert [h["external_id"] for h in query.json()["hits"]] == ["A-2"]


async def test_search_run_never_returns_another_organisations_documents() -> None:
    client, _ = _scripted()
    await client.post(UPSERT, json=_upsert())
    other = await client.post(SEARCH, json=_search(organization_id=OTHER))
    assert other.status_code == 200
    assert other.json()["hits"] == []
    assert other.json()["usage"]["cost_micros"] == 0
    poisoned = await client.post(
        UPSERT, json=_upsert(_document("B-1", LOGIN), organization_id=OTHER)
    )
    assert poisoned.status_code == 200
    mine = await client.post(SEARCH, json=_search())
    assert {h["external_id"] for h in mine.json()["hits"]} == {"A-1", "A-2"}


async def test_search_run_refuses_at_the_door() -> None:
    client, _ = _scripted()
    await client.post(UPSERT, json=_upsert())
    scanned = await client.post(SEARCH, json=_search("mail me at someone@example.com"))
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    capped, _ = _scripted(tenant_budget_default_micros_per_day=1)
    budget = await capped.post(SEARCH, json=_search())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"


class _BrokenStorage(MemoryStorage):
    async def count_chunks(self, organization_id: object, corpus: object) -> int:
        raise StorageUnavailableError("broken")


async def test_search_run_reports_an_unavailable_index() -> None:
    provider = ScriptedProvider(["{}"])
    settings = make_settings()
    runtime = make_runtime(provider, settings, _BrokenStorage(FrozenClock()))
    client = _client(runtime, settings)
    response = await client.post(SEARCH, json=_search())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai.index.unavailable"
    assert response.json()["error"]["retry_after_ms"] == 5000
    upsert = await client.post(UPSERT, json=_upsert())
    assert upsert.json()["error"]["code"] == "ai.index.unavailable"


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (Fault(status=503), "ai.provider.unavailable"),
        (Fault(raises=httpx.ReadTimeout), "ai.provider.timeout"),
        (Fault(status=429), "ai.provider.quota"),
        (Fault(status=400), "ai.provider.rejected"),
    ],
    ids=["unavailable", "timeout", "quota", "rejected"],
)
async def test_search_run_provider_failures_on_upsert(fault: Fault, code: str) -> None:
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
    response = await client.post(UPSERT, json=_upsert())
    assert response.json()["error"]["code"] == code
