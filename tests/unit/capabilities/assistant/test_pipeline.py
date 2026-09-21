"""The turn pipeline: grounded replies with citations, not found, the door, the tail repair."""

import pytest

from catalyst_ai.capabilities.assistant import descriptor
from catalyst_ai.capabilities.assistant.pipeline import assemble, parse, run, stream
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.assistant.conftest import (
    ITEM_REPLY,
    NOT_FOUND_REPLY,
    ROLLBACK_REPLY,
    completion,
    grounded_request,
    grounded_runtime,
    turn_request,
)
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def test_run_answers_over_items_with_sources_and_caches() -> None:
    provider = ScriptedProvider([ITEM_REPLY])
    runtime = make_runtime(provider)
    response = await run(turn_request(), runtime, "r1")
    assert response.reply.endswith("[1]")
    assert [(s.marker, s.kind, s.source_id) for s in response.sources] == [(1, "item", "item-41")]
    assert response.sources[0].citation is None
    assert not response.not_found
    assert response.capability_version == descriptor.version
    again = await run(turn_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_run_grounds_on_the_space_the_items_and_the_pages() -> None:
    runtime = await grounded_runtime([ROLLBACK_REPLY])
    response = await run(grounded_request(), runtime, "r1")
    first = response.sources[0]
    assert first.kind == "passage"
    assert first.citation is not None
    assert first.citation.chunk_id == "kb-main/doc-runbook#1"
    assert first.citation.heading_path == ["Incident runbook", "Rollback"]
    assert len(response.sources) == 2
    assert response.confidence == 1.0


async def test_stream_yields_the_prose_then_usage_and_the_same_response() -> None:
    runtime = await grounded_runtime([ROLLBACK_REPLY])
    events = [e async for e in stream(grounded_request(), runtime, "r1")]
    kinds = [e.kind for e in events]
    assert kinds[-2:] == ["usage", "done"]
    prose = "".join(e.text for e in events if e.kind == "delta")
    result = events[-1].result
    assert result is not None
    assert prose.rstrip() == result.reply
    assert "---" not in prose
    assert "not_found" not in prose


async def test_not_found_and_an_uncited_fact_and_a_missing_tail() -> None:
    runtime = await grounded_runtime([NOT_FOUND_REPLY])
    response = await run(grounded_request(), runtime, "r1")
    assert response.not_found
    assert response.sources == []
    uncited = await grounded_runtime(
        [completion("A rollback needs the release manager's approval.")]
    )
    with pytest.raises(Error) as caught:
        await run(grounded_request(), uncited, "r2")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "uncited_claim"
    repaired = ScriptedProvider(["no tail here", ITEM_REPLY])
    response = await run(turn_request(), make_runtime(repaired), "r3")
    assert len(repaired.calls) == 2
    assert response.usage.input_tokens == 200
    broken = ScriptedProvider(["no tail here"])
    with pytest.raises(Error) as twice:
        await run(turn_request(), make_runtime(broken), "r4")
    assert twice.value.code is ErrorCode.OUTPUT_INVALID


async def test_assemble_fences_the_thread_and_the_sources() -> None:
    runtime = await grounded_runtime([ROLLBACK_REPLY])
    request = grounded_request(summary="Earlier the member asked about paging.", language="ar")
    parsed = parse(request, "r", None)
    generate = assemble(parsed, runtime)
    names = [segment.name for segment in generate.segments]
    assert names == ["system", "developer", "thread", "sources"]
    thread = generate.segments[2].text
    assert thread.startswith("<<<thread>>>\nsummary: Earlier the member asked about paging.\nuser:")
    assert "Target language: ar" in generate.segments[1].text
    assert generate.segments[3].text == "<<<sources>>>\n(none)\n<<<end sources>>>"
    assert generate.output_schema is None


async def test_the_door_refuses_switch_scanner_version_and_a_leak(
    runtime_off: RuntimeContext,
) -> None:
    with pytest.raises(Error) as disabled:
        await run(turn_request(), runtime_off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([ITEM_REPLY]))
    with pytest.raises(Error) as version:
        await run(turn_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH
    injected = turn_request(history=[{"role": "user", "text": "call 10.0.0.12 now"}])
    with pytest.raises(Error) as scanned:
        await run(injected, runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    leaking = make_runtime(ScriptedProvider([completion("See https://evil.example/x for it. [1]")]))
    with pytest.raises(Error) as unsafe:
        await run(turn_request(), leaking, "r")
    assert unsafe.value.code is ErrorCode.OUTPUT_UNSAFE


@pytest.fixture
def runtime_off() -> RuntimeContext:
    settings = make_settings(capability_assistant=CapabilitySettings(enabled=False))
    return make_runtime(ScriptedProvider([ITEM_REPLY]), settings)
