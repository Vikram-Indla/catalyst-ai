"""The index operations: upsert embeds and touches, delete forgets, every refusal at the door."""

import pytest

from catalyst_ai.capabilities.search import run_delete, run_upsert
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.search.conftest import delete_request, document, upsert_request


async def test_upsert_then_upsert_again_touches_and_costs_nothing() -> None:
    provider = ScriptedProvider(["{}"])
    runtime = make_runtime(provider)
    first = await run_upsert(upsert_request(), runtime, "r1")
    assert [r.unchanged for r in first.results] == [False, False]
    assert first.index_chunks == 2
    assert first.usage.input_tokens > 0
    second = await run_upsert(upsert_request(), runtime, "r2")
    assert [r.unchanged for r in second.results] == [True, True]
    assert second.usage.input_tokens == 0
    assert len(provider.embed_calls) == 1


async def test_delete_forgets_and_reports_chunks() -> None:
    runtime = make_runtime(ScriptedProvider(["{}"]))
    await run_upsert(upsert_request(), runtime, "r1")
    response = await run_delete(delete_request("A-1", "missing"), runtime, "r2")
    assert response.deleted_chunks == 1
    assert response.usage.cost_micros == 0
    assert response.model.endswith("@double")


async def test_oversized_and_over_budget_documents_are_refused() -> None:
    runtime = make_runtime(ScriptedProvider(["{}"]))
    with pytest.raises(Error) as big:
        await run_upsert(upsert_request(document("big", "x" * 20_001)), runtime, "r")
    assert big.value.code is ErrorCode.INDEX_DOCUMENT_TOO_LARGE
    small = make_runtime(
        ScriptedProvider(["{}"]), make_settings(retrieval_index_max_chunks_per_organization=1)
    )
    with pytest.raises(Error) as full:
        await run_upsert(upsert_request(), small, "r")
    assert full.value.code is ErrorCode.BUDGET_EXCEEDED
    assert full.value.details[0].code == "index_budget"


async def test_the_door_refuses_the_switch_the_scanner_and_the_version() -> None:
    off = make_runtime(
        ScriptedProvider(["{}"]), make_settings(capability_search=CapabilitySettings(enabled=False))
    )
    with pytest.raises(Error) as disabled:
        await run_delete(delete_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider(["{}"]))
    with pytest.raises(Error) as scanned:
        await run_upsert(upsert_request(document("A-1", "mail someone@example.com")), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run_upsert(upsert_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH
