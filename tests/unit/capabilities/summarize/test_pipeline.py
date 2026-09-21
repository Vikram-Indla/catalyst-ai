"""The summarize pipeline over the scripted provider: the thread as data, the door, the cache."""

import pytest

from catalyst_ai.capabilities.summarize import descriptor, run
from catalyst_ai.capabilities.summarize.pipeline import assemble, parse, status_text, thread_text
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.summarize.conftest import make_request, summary_text


async def test_run_returns_the_summary_with_range_tokens_and_versions() -> None:
    provider = ScriptedProvider([summary_text()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert response.summary.startswith("p1 found")
    assert response.participants_mentioned == ["p1", "p2", "p3"]
    assert response.covered_range.first_id == "c1"
    assert response.covered_range.last_id == "c4"
    assert response.covered_range.count == 4
    assert response.empty_reason is None
    assert response.capability_version == descriptor.version
    assert response.model.endswith("@double")
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


def test_thread_and_status_text_are_one_line_per_entry() -> None:
    request = make_request(
        status_changes=[
            {
                "participant": "p2",
                "from_status": "To Do",
                "to_status": "Done",
                "at": "2026-09-01T10:00:00+00:00",
            }
        ]
    )
    lines = thread_text(request).splitlines()
    assert lines[0].startswith("[c1] p1 @ 2026-09-01T09:00:00+00:00: ")
    assert len(lines) == 4
    assert status_text(request) == "p2 moved it from To Do to Done at 2026-09-01T10:00:00+00:00"
    assert status_text(make_request()) == ""


def test_assemble_fences_the_thread_and_names_the_mode_and_length() -> None:
    parsed = parse(make_request(target_words=100, language="ar"), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([summary_text()])))
    developer = generate.segments[1].text
    assert "Mode: comments" in developer
    assert "about 100 words; never more than 150" in developer
    assert "Target language: ar" in developer
    assert "Decisions made" in developer
    thread = generate.segments[2].text
    assert thread.startswith("<<<thread>>>")
    assert "PRJ-42" in thread
    assert generate.output_schema is not None
    assert generate.alias.value == descriptor.alias


async def test_the_door_refuses_switch_scanner_and_version() -> None:
    off = make_runtime(
        ScriptedProvider([summary_text()]),
        make_settings(capability_summarize=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([summary_text()]))
    items = [
        {
            "id": "c1",
            "participant": "p1",
            "at": "2026-09-01T09:00:00+00:00",
            "text": "mail me at someone@example.com",
        }
    ]
    with pytest.raises(Error) as scanned:
        await run(make_request(items=items), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run(make_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_a_summary_naming_an_unknown_participant_is_unsafe() -> None:
    provider = ScriptedProvider([summary_text("p1 and p9 agreed to ship.", ("p1", "p9"))])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
    assert caught.value.details[0].code == "participant_not_in_thread"


async def test_an_empty_thread_yields_the_reason_and_no_call_content() -> None:
    provider = ScriptedProvider([summary_text("", (), "nothing_to_summarize")])
    response = await run(make_request(items=[]), make_runtime(provider), "r")
    assert response.summary == ""
    assert response.empty_reason == "nothing_to_summarize"
    assert response.covered_range.count == 0
    assert response.participants_mentioned == []


async def test_a_standup_names_every_token_and_refuses_a_foreign_one() -> None:
    window = {"from_at": "2026-09-01T00:00:00+00:00", "to_at": "2026-09-01T23:59:00+00:00"}
    entries = [
        {"participant": "p1", "done": ["export step"], "doing": [], "blocked": ["ops"]},
        {"participant": "p3", "done": [], "doing": ["flag"], "blocked": []},
    ]
    good = summary_text("p1 and p3 reported.", ("p1", "p3"), standup=entries)
    response = await run(
        make_request(mode="standup", window=window), make_runtime(ScriptedProvider([good])), "r"
    )
    assert [e.participant for e in response.standup] == ["p1", "p2", "p3"]
    assert response.standup[0].blocked == ["ops"]
    assert response.standup[1].done == []
    assert response.participants_mentioned == ["p1", "p3"]
    foreign = summary_text("p1 reported.", ("p1",), standup=[{**entries[0], "participant": "p9"}])
    with pytest.raises(Error) as caught:
        await run(
            make_request(mode="standup", window=window),
            make_runtime(ScriptedProvider([foreign])),
            "r",
        )
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE


async def test_a_digest_echoes_the_counts_and_needs_them() -> None:
    window = {"from_at": "2026-09-01T00:00:00+00:00", "to_at": "2026-09-01T23:59:00+00:00"}
    counts = [{"kind": "work_item", "count": 41}, {"kind": "release", "count": 0}]
    groups = [{"kind": "work_item", "changes": ["PRJ-42 moved to Done"]}]
    text = summary_text("PRJ-42 moved.", (), digest=groups)
    response = await run(
        make_request(mode="digest", window=window, counts=counts),
        make_runtime(ScriptedProvider([text])),
        "r",
    )
    assert [(g.kind, g.count) for g in response.digest] == [("work_item", 41), ("release", 0)]
    assert response.digest[0].changes == ["PRJ-42 moved to Done"]
    with pytest.raises(Error) as caught:
        await run(
            make_request(mode="digest", window=window), make_runtime(ScriptedProvider([text])), "r"
        )
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert caught.value.details[0].code == "counts_required"
