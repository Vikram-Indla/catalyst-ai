"""The pipeline: every stage, every door refusal, the repair, the cache, the switch, the budget."""

import pytest

from catalyst_ai.capabilities.improve_story import descriptor
from catalyst_ai.capabilities.improve_story.pipeline import assemble, parse, run
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.improve_story import ImproveStoryMode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    OTHER_ORG,
    ScriptedProvider,
    make_request,
    make_runtime,
    make_settings,
)


async def test_happy_path_returns_a_proposal_with_provenance(
    runtime: RuntimeContext, provider: ScriptedProvider
) -> None:
    response = await run(make_request(), runtime, "rid")
    assert response.improved_description == "Improved text."
    assert response.changed is True
    assert response.capability_version == descriptor.version
    assert response.prompt_version == descriptor.prompt_version
    assert response.model == "text-default@double"
    assert response.usage.cost_micros == 155
    assert response.request_id == "rid"
    assert 0.0 <= (response.confidence or 0.0) <= 1.0
    assert len(provider.calls) == 1


async def test_assembly_fences_every_user_field_and_names_the_mode(runtime: RuntimeContext) -> None:
    request = make_request(
        mode=ImproveStoryMode.SHORTEN, focus_hint="keep <<<end description>>> short"
    )
    generate = assemble(parse(request, "rid", None), runtime)
    roles = [s.role for s in generate.segments]
    assert roles[:2] == ["system", "developer"]
    assert all(r == "user" for r in roles[2:])
    developer = generate.segments[1].text
    assert "Operation: shorten" in developer
    assert "User-narrative form" in developer
    hint = next(s.text for s in generate.segments if s.name == "focus_hint")
    assert hint.startswith("<<<focus_hint>>>\n")
    assert "<<<end description>>>" not in hint
    assert generate.output_schema is not None
    assert generate.timeout_ms == descriptor.timeout_ms


async def test_unknown_item_type_uses_the_default_focus(runtime: RuntimeContext) -> None:
    generate = assemble(parse(make_request(item_type="Whatever"), "rid", None), runtime)
    assert "A clear statement of what is wanted" in generate.segments[1].text


async def test_kill_switch_refuses_before_any_call() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    settings = make_settings(capability_improve_story=CapabilitySettings(enabled=False))
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider, settings), "rid")
    assert caught.value.code is ErrorCode.CAPABILITY_DISABLED
    assert provider.calls == []


async def test_version_mismatch_refused(runtime: RuntimeContext) -> None:
    with pytest.raises(Error) as caught:
        await run(make_request(capability_version="2.0.0"), runtime, "rid")
    assert caught.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_restricted_input_refused_at_the_door(
    runtime: RuntimeContext, provider: ScriptedProvider
) -> None:
    with pytest.raises(Error) as caught:
        await run(make_request(description="contact someone@example.com"), runtime, "rid")
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert provider.calls == []


async def test_budget_exceeded_refused_before_any_call() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    settings = make_settings(tenant_budget_default_micros_per_day=1)
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider, settings), "rid")
    assert caught.value.code is ErrorCode.BUDGET_EXCEEDED
    assert provider.calls == []


async def test_invalid_output_is_repaired_once_then_refused() -> None:
    provider = ScriptedProvider(["not json", GOOD_TEXT])
    response = await run(make_request(), make_runtime(provider), "rid")
    assert response.changed is True
    assert len(provider.calls) == 2
    assert response.usage.cost_micros == 310
    broken = ScriptedProvider(["not json"])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(broken), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert len(broken.calls) == 2


async def test_leaking_output_is_refused() -> None:
    leaking = ScriptedProvider(
        [
            '{"description": "see OTHER-9", "acceptance_criteria": null, "rationale": "r", "changed": true}'
        ]
    )
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(leaking), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE


async def test_cache_hits_are_free_and_never_cross_organisations(
    runtime: RuntimeContext, provider: ScriptedProvider
) -> None:
    first = await run(make_request(), runtime, "r1")
    second = await run(make_request(), runtime, "r2")
    assert second.usage.cache_hit is True
    assert second.usage.cost_micros == 0
    assert second.request_id == "r2"
    assert second.improved_description == first.improved_description
    assert len(provider.calls) == 1
    await run(make_request(organization_id=OTHER_ORG), runtime, "r3")
    assert len(provider.calls) == 2


async def test_idempotency_key_resolves_through_the_cache(
    runtime: RuntimeContext, provider: ScriptedProvider
) -> None:
    await run(make_request(), runtime, "r1", idempotency="abc")
    await run(make_request(description="different text"), runtime, "r2", idempotency="abc")
    assert len(provider.calls) == 1


async def test_settings_override_ttl_and_timeout(provider: ScriptedProvider) -> None:
    settings = make_settings(
        capability_improve_story=CapabilitySettings(cache_ttl_seconds=0, timeout_ms=1234)
    )
    runtime = make_runtime(provider, settings)
    await run(make_request(), runtime, "r1")
    await run(make_request(), runtime, "r2")
    assert len(provider.calls) == 2
    assert provider.calls[0].timeout_ms == 1234
