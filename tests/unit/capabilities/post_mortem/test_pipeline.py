"""The post-mortem pipeline over the scripted provider: the data, the door, the cache."""

import pytest

from catalyst_ai.capabilities.post_mortem import descriptor, run
from catalyst_ai.capabilities.post_mortem.pipeline import (
    assemble,
    incident_text,
    parse,
    timeline_text,
)
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.post_mortem.conftest import TIMELINE, draft_text, make_request


async def test_run_returns_the_draft_with_versions_and_caches_it() -> None:
    provider = ScriptedProvider([draft_text()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert [f.source_id for f in response.facts] == ["ev-1", "ev-2", "ev-4"]
    assert response.capability_version == descriptor.version
    assert response.model.endswith("@double")
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


def test_texts_are_one_line_per_entry_and_fact() -> None:
    lines = timeline_text(make_request()).splitlines()
    assert (
        lines[0]
        == "[ev-1] p1 @ 2026-09-14T08:01:00+00:00: Alert fired: error rate above 5% on the search endpoint."
    )
    assert lines[3].startswith("[ev-4] @ ")
    incident = incident_text(
        make_request(
            incident={
                "title": "Search cluster degraded",
                "started_at": "2026-09-14T08:00:00+00:00",
                "impact": "Search slow",
            }
        )
    )
    assert incident.splitlines() == [
        "title: Search cluster degraded",
        "started: 2026-09-14T08:00:00+00:00",
        "impact: Search slow",
    ]


def test_assemble_fences_the_incident_and_the_timeline() -> None:
    parsed = parse(make_request(language="ar"), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([draft_text()])))
    assert "Target language: ar" in generate.segments[1].text
    assert generate.segments[2].text.startswith("<<<incident>>>\ntitle: Search cluster degraded")
    assert "[ev-2] p2 @" in generate.segments[3].text
    assert generate.output_schema is not None
    bare = assemble(
        parse(make_request(timeline=[]), "rid", None),
        make_runtime(ScriptedProvider([draft_text()])),
    )
    assert "<<<timeline>>>\n(none)" in bare.segments[3].text


async def test_the_door_refuses_switch_scanner_and_version() -> None:
    off = make_runtime(
        ScriptedProvider([draft_text()]),
        make_settings(capability_post_mortem=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([draft_text()]))
    leaking = [{**TIMELINE[0], "text": "paged 10.0.0.12 by hand"}]
    with pytest.raises(Error) as scanned:
        await run(make_request(timeline=leaking), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run(make_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_a_fact_with_a_foreign_link_is_unsafe() -> None:
    text = draft_text(facts=[{"source_id": "ev-1", "text": "See https://evil.example/x"}])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(ScriptedProvider([text])), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
