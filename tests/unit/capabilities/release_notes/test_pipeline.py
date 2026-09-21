"""The release-notes pipeline over the scripted provider: the data, the door, the cache."""

import pytest

from catalyst_ai.capabilities.release_notes import descriptor, run
from catalyst_ai.capabilities.release_notes.pipeline import assemble, changes_text, parse
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.release_notes.conftest import CHANGES, make_request, notes_text


async def test_run_returns_the_notes_with_versions_and_caches_them() -> None:
    provider = ScriptedProvider([notes_text()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert [s.kind for s in response.sections] == ["story", "bug", "task"]
    assert response.capability_version == descriptor.version
    assert response.model.endswith("@double")
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


def test_changes_text_is_one_line_per_change_with_id_key_kind_and_state() -> None:
    lines = changes_text(make_request()).splitlines()
    assert lines[0] == "[chg-1] PRJ-101 (story, done by p1): Change number 1 for the board export"
    assert lines[2].startswith("[chg-3] PRJ-103 (story, in_progress by p2): ")
    assert changes_text(make_request(changes=[])) == ""


def test_assemble_fences_the_release_and_the_changes() -> None:
    parsed = parse(make_request(mode="summary", audience="customer", language="ar"), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([notes_text()])))
    developer = generate.segments[1].text
    assert "Mode: summary" in developer
    assert "Audience: customer" in developer
    assert "Target language: ar" in developer
    assert "attention" in developer
    assert generate.segments[2].text.startswith("<<<release>>>\nname: Board export")
    assert "[chg-1]" in generate.segments[3].text
    assert generate.alias.value == descriptor.alias


async def test_the_door_refuses_switch_scanner_and_version() -> None:
    off = make_runtime(
        ScriptedProvider([notes_text()]),
        make_settings(capability_release_notes=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([notes_text()]))
    leaking = [{**CHANGES[0], "title": "mail someone@example.com about it"}]
    with pytest.raises(Error) as scanned:
        await run(make_request(changes=leaking), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run(make_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_an_entry_with_a_foreign_link_is_unsafe() -> None:
    text = notes_text(
        sections=[
            {
                "kind": "story",
                "entries": [{"source_id": "chg-1", "text": "See https://evil.example/x"}],
            }
        ],
        highlights=[],
    )
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(ScriptedProvider([text])), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
