"""The unfurl pipeline: a card from the text, the cache, the door, an invented fact dropped."""

import pytest

from catalyst_ai.capabilities.unfurl import descriptor
from catalyst_ai.capabilities.unfurl.pipeline import assemble, parse, run
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.unfurl.conftest import card_text, unfurl_request


async def test_run_builds_the_card_and_caches() -> None:
    provider = ScriptedProvider([card_text()])
    runtime = make_runtime(provider)
    response = await run(unfurl_request(), runtime, "r1")
    assert response.title == "Login button broken on mobile"
    assert [(f.label, f.value) for f in response.facts] == [
        ("status", "in_progress"),
        ("since", "2026-09-10"),
    ]
    assert response.confidence == 1.0
    assert response.capability_version == descriptor.version
    again = await run(unfurl_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_an_invented_fact_is_dropped_and_lowers_confidence() -> None:
    invented = [
        {"label": "owner", "value": "the platform team"},
        {"label": "status", "value": "in_progress"},
    ]
    runtime = make_runtime(ScriptedProvider([card_text(invented)]))
    response = await run(unfurl_request(), runtime, "r")
    assert [(f.label, f.value) for f in response.facts] == [("status", "in_progress")]
    assert response.confidence == 0.85
    bare = await run(
        unfurl_request(text=None), make_runtime(ScriptedProvider([card_text([])])), "r"
    )
    assert bare.facts == []
    assert bare.confidence == 0.9


async def test_assemble_fences_the_title_and_the_text() -> None:
    runtime = make_runtime(ScriptedProvider([card_text()]))
    generate = assemble(parse(unfurl_request(language="ar"), "r", None), runtime)
    names = [segment.name for segment in generate.segments]
    assert names == ["system", "developer", "title", "text"]
    assert "Kind: item" in generate.segments[1].text
    assert "Target language: ar" in generate.segments[1].text
    assert generate.segments[3].text.startswith("<<<text>>>\nstatus: in_progress\nThe login")
    empty = assemble(parse(unfurl_request(text=None, status=None), "r", None), runtime)
    assert empty.segments[3].text == "<<<text>>>\n(none)\n<<<end text>>>"


async def test_the_door_refuses_switch_version_and_a_leak() -> None:
    settings = make_settings(capability_unfurl=CapabilitySettings(enabled=False))
    with pytest.raises(Error) as disabled:
        await run(unfurl_request(), make_runtime(ScriptedProvider([card_text()]), settings), "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([card_text()]))
    with pytest.raises(Error) as version:
        await run(unfurl_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH
    leaking = make_runtime(ScriptedProvider([card_text(summary="See https://evil.example/x")]))
    with pytest.raises(Error) as unsafe:
        await run(unfurl_request(), leaking, "r")
    assert unsafe.value.code is ErrorCode.OUTPUT_UNSAFE
