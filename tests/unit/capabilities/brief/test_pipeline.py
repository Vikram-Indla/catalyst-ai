"""The brief pipeline: the chain fenced, the language named, an empty chain briefing nothing."""

import pytest

from catalyst_ai.capabilities.brief.pipeline import assemble, parse, run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.brief.conftest import answer, brief_request
from tests.unit.capabilities.improve_story.conftest import ScriptedProvider, make_runtime


async def test_a_grounded_briefing_is_returned_and_cached() -> None:
    provider = ScriptedProvider([answer()])
    runtime = make_runtime(provider)
    response = await run(brief_request(), runtime, "r1")
    assert [s.cites for s in response.summary] == [["O-1"], ["P-1"]]
    assert response.risks[0].text == "Portal rebuild is blocked."
    again = await run(brief_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_the_chain_is_fenced_and_the_language_and_length_named() -> None:
    request = brief_request(locale="ar", max_sentences=3)
    generate = assemble(parse(request, "r", None), make_runtime(ScriptedProvider([answer()])))
    developer = generate.segments[1].text
    assert "Language: Arabic" in developer
    assert "at most 3 sentences" in developer
    chain = next(s.text for s in generate.segments if s.name == "chain")
    assert chain.startswith("<<<chain>>>\n")


async def test_an_unseen_number_is_refused_after_the_model_answers() -> None:
    lying = answer(risks=[{"text": "Progress is 100%.", "cites": ["O-1"]}])
    with pytest.raises(Error) as caught:
        await run(brief_request(), make_runtime(ScriptedProvider([lying])), "r")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID


async def test_an_empty_chain_briefs_nothing_in_the_requests_language() -> None:
    chain = {"theme": {"id": "T-1", "title": "t"}}
    empty = answer(summary=[], risks=[], asks=[], empty_reason="nothing_to_brief")
    response = await run(
        brief_request(chain=chain, locale="ar"), make_runtime(ScriptedProvider([empty])), "r"
    )
    assert response.empty_reason == "nothing_to_brief"
    assert response.summary == []
    assert response.unsupported == ["لا تحمل السلسلة أي هدف أو مشروع أو ملاحظة"]
