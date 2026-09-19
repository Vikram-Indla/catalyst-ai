"""The generate-children pipeline: assembly, the door, wrong levels, the cache, empty results."""

import pytest

from catalyst_ai.capabilities.generate_children import descriptor
from catalyst_ai.capabilities.generate_children.pipeline import assemble, parse, run
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.generate_children import GenerateTarget, Sibling
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.generate_children.conftest import (
    candidates_text,
    empty_text,
    make_request,
)
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def test_happy_path_returns_typed_candidates() -> None:
    provider = ScriptedProvider([candidates_text("Share a filter with a team", "Unshare a filter")])
    response = await run(make_request(), make_runtime(provider), "rid")
    assert [c.type for c in response.candidates] == ["story", "story"]
    assert response.empty_reason is None
    assert response.capability_version == descriptor.version
    assert response.model == "text-default@double"
    assert len(provider.calls) == 1


async def test_assembly_names_the_target_level_and_fences_lists() -> None:
    request = make_request(
        target=GenerateTarget.CHILDREN,
        siblings=[Sibling(title="Existing <<<end siblings>>> child")],
        source_texts=["a source"],
    )
    generate = assemble(parse(request, "rid", None), make_runtime(ScriptedProvider(["x"])))
    developer = generate.segments[1].text
    assert "Target: children" in developer
    assert "<<<child_level>>>\nstory\n<<<end child_level>>>" in developer
    assert "Propose the next level of work" in developer
    siblings = next(s.text for s in generate.segments if s.name == "siblings")
    assert siblings.count("<<<end siblings>>>") == 1
    assert generate.timeout_ms == descriptor.timeout_ms
    assert generate.max_output_tokens == descriptor.max_output_tokens


async def test_wrong_level_output_is_output_invalid_with_hierarchy_violation() -> None:
    provider = ScriptedProvider([candidates_text("a", level="task")])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "hierarchy_violation"


async def test_skipping_a_level_is_refused_at_the_door_before_any_call() -> None:
    provider = ScriptedProvider([candidates_text("a")])
    with pytest.raises(Error) as caught:
        await run(make_request(child_level="task"), make_runtime(provider), "rid")
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert provider.calls == []


async def test_empty_result_carries_its_reason() -> None:
    provider = ScriptedProvider([empty_text("siblings_cover_it")])
    response = await run(make_request(), make_runtime(provider), "rid")
    assert response.candidates == []
    assert response.empty_reason == "siblings_cover_it"


async def test_kill_switch_and_cache() -> None:
    provider = ScriptedProvider([candidates_text("a")])
    settings = make_settings(capability_generate_children=CapabilitySettings(enabled=False))
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider, settings), "rid")
    assert caught.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(provider)
    await run(make_request(), runtime, "r1")
    second = await run(make_request(), runtime, "r2")
    assert second.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_leaking_candidate_is_refused() -> None:
    provider = ScriptedProvider([candidates_text("See OTHER-9 for details")])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
