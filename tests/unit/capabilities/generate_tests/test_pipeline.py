"""The generate-tests pipeline over the scripted provider: the data, the door, the cache."""

import pytest

from catalyst_ai.capabilities.generate_tests import descriptor, run
from catalyst_ai.capabilities.generate_tests.pipeline import (
    assemble,
    cases_text,
    criteria_text,
    parse,
    story_text,
)
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.generate_tests.conftest import (
    CASES,
    CRITERIA,
    EXISTING,
    OUTLINE,
    TABLES,
    make_request,
)
from tests.unit.capabilities.generate_tests.conftest import (
    cases_text as completion,
)
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def test_run_returns_the_cases_with_versions_and_caches_them() -> None:
    provider = ScriptedProvider([completion()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert len(response.cases) == 3
    assert response.capability_version == descriptor.version
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


def test_texts_are_one_line_per_thing() -> None:
    request = make_request(cases=EXISTING)
    assert story_text(request).splitlines() == [
        "key: PRJ-7",
        "title: Export the board to CSV",
        "description: As a lead",
    ]
    assert criteria_text(request).splitlines()[0] == "[ac-1] Every visible column is exported"
    lines = cases_text(request).splitlines()
    assert lines[0] == "[tc-1] Verify every visible column is exported — Columns"
    assert lines[1] == "  step: Export the board -> The file has every column"
    assert lines[2] == "[tc-2] Verify archived items stay out"


def test_assemble_fences_the_story_the_criteria_and_the_cases() -> None:
    parsed = parse(make_request(language="ar", max_cases=4), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([completion()])))
    developer = generate.segments[1].text
    assert "Mode: cases" in developer
    assert "At most this many cases: 4" in developer
    assert "Target language: ar" in developer
    assert generate.segments[2].text.startswith("<<<story>>>")
    assert "[ac-2]" in generate.segments[3].text
    assert "<<<cases>>>\n(none)" in generate.segments[4].text


async def test_artefacts_need_cases_and_the_door_refuses_the_rest() -> None:
    runtime = make_runtime(ScriptedProvider([completion([], OUTLINE, TABLES)]))
    with pytest.raises(Error) as no_cases:
        await run(make_request(mode="artefacts", criteria=[]), runtime, "r")
    assert no_cases.value.code is ErrorCode.INPUT_REJECTED
    assert no_cases.value.details[0].code == "cases_required"
    response = await run(make_request(mode="artefacts", criteria=[], cases=EXISTING), runtime, "r")
    assert response.data_tables[0].name == "Columns"
    off = make_runtime(
        ScriptedProvider([completion()]),
        make_settings(capability_generate_tests=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    scanned = make_runtime(ScriptedProvider([completion()]))
    leaking = [{**CRITERIA[0], "text": "mail someone@example.com"}]
    with pytest.raises(Error) as rejected:
        await run(make_request(criteria=leaking), scanned, "r")
    assert rejected.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run(make_request(capability_version="2.0.0"), scanned, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_a_case_with_a_foreign_link_is_unsafe() -> None:
    text = completion([{**CASES[0], "then": "See https://evil.example/x"}])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(ScriptedProvider([text])), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
