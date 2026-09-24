"""A governed record's rewrite keeps its facts, its glossary and Latin digits, or is refused."""

import json

import pytest

from catalyst_ai.capabilities.improve_story.governed import (
    FACT_ADDED,
    FACT_LOST,
    TERM_LOST,
    facts,
    problems,
)
from catalyst_ai.capabilities.improve_story.pipeline import assemble, parse, run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.improve_story import ImproveStoryMode, ImproveStoryRequest
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_request,
    make_runtime,
)

KR = "increase online permit applications from ٤٠٪ to ٧٠٪ by Q4 2026"
RECORD = {
    "focus": "A key result: measurable wording of one outcome.",
    "context": [{"label": "Objective", "text": "Residents get permits without visiting"}],
    "glossary": ["online permit"],
}


def record_request(description: str = KR, **overrides: object) -> ImproveStoryRequest:
    values: dict[str, object] = {
        "item_type": "key_result",
        "title": "Online permit share",
        "description": description,
        "record": RECORD,
        "focus_hint": "add a due date and a 90% stretch target",
    }
    values.update(overrides)
    return make_request(**values)


def answer(description: str) -> str:
    output = {
        "description": description,
        "acceptance_criteria": None,
        "rationale": "Tightened the wording.",
        "changed": True,
    }
    return json.dumps(output, ensure_ascii=False)


def test_facts_read_every_script_of_digits_as_latin() -> None:
    assert facts("from ٤٠٪ to 70%, see https://a.example/x and @p2") == {
        "40",
        "70",
        "https://a.example/x",
        "@p2",
    }


def test_a_rewrite_that_keeps_the_facts_has_no_problem() -> None:
    kept = "Increase online permit applications from 40% to 70% by Q4 2026."
    assert problems(record_request(), kept) == []


def test_a_number_the_hint_asked_for_is_still_an_added_fact() -> None:
    added = "Increase online permit applications from 40% to 90% by Q4 2026, due 2026-12-31."
    found = problems(record_request(), added)
    assert (FACT_ADDED, "90") in found
    assert (FACT_ADDED, "12") in found
    assert found[-1] == (FACT_LOST, "70")


def test_a_new_link_or_participant_is_an_added_fact() -> None:
    added = "Increase online permit applications from 40% to 70% by Q4 2026, owner @p9, see https://x.example."
    found = {what for _, what in problems(record_request(), added)}
    assert {"@p9", "https://x.example"} <= found


def test_a_glossary_term_the_source_uses_must_survive_exactly() -> None:
    lost = "Increase web permit applications from 40% to 70% by Q4 2026."
    assert problems(record_request(), lost) == [(TERM_LOST, "online permit")]


def test_the_context_is_a_source_of_facts_and_the_focus_is_not() -> None:
    record = {**RECORD, "context": [{"label": "Period", "text": "FY2026"}], "focus": "Use 3 lines"}
    request = record_request(description="raise online permit use", record=record)
    assert problems(request, "Raise online permit use in FY2026.") == []
    assert problems(request, "Raise online permit use in 3 steps.") == [(FACT_ADDED, "3")]


def test_without_a_record_nothing_is_checked() -> None:
    assert problems(make_request(), "a 99% new number") == []


async def test_a_record_run_returns_latin_digits() -> None:
    provider = ScriptedProvider(
        [answer("Increase online permit applications from ٤٠٪ to ٧٠٪ by Q4 2026.")]
    )
    response = await run(record_request(), make_runtime(provider), "rid")
    assert "from 40٪ to 70٪ by Q4 2026" in response.improved_description
    assert not any("٠" <= ch <= "٩" for ch in response.improved_description)


async def test_a_record_run_that_adds_a_target_is_refused() -> None:
    provider = ScriptedProvider(
        [answer("Increase online permit applications from 40% to 90% by Q4 2026.")]
    )
    with pytest.raises(Error) as raised:
        await run(record_request(), make_runtime(provider), "rid")
    assert raised.value.code is ErrorCode.OUTPUT_INVALID
    assert [d.message for d in raised.value.details] == ["fact_added: 90", "fact_lost: 70"]


async def test_the_record_travels_as_data_after_the_item_fields() -> None:
    generate = assemble(parse(record_request(), "rid", None), make_runtime(ScriptedProvider([""])))
    names = [s.name for s in generate.segments]
    assert names[-4:] == ["record", "record_focus", "record_context", "glossary"]
    assert "The focus the product gives" in generate.segments[1].text
    focus = next(s.text for s in generate.segments if s.name == "record_focus")
    assert focus.startswith("<<<record_focus>>>\n")


async def test_a_request_without_a_record_is_assembled_as_before() -> None:
    generate = assemble(parse(make_request(), "rid", None), make_runtime(ScriptedProvider([""])))
    names = {s.name for s in generate.segments}
    assert names.isdisjoint({"record", "record_focus", "record_context", "glossary"})


def test_a_reply_owes_the_source_no_glossary_term() -> None:
    request = record_request(
        mode=ImproveStoryMode.REPLY, comment={"participant": "p1", "text": "Is online permit live?"}
    )
    assert problems(request, "@p1 not yet.") == []


def test_a_shorter_wording_that_drops_the_target_has_changed_it() -> None:
    dropped = "Increase online permit applications by Q4 2026."
    assert problems(record_request(), dropped) == [(FACT_LOST, "40"), (FACT_LOST, "70")]
