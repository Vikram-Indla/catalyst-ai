"""The generate pipeline: sections traced to sources, uncited refused, thin sources, the cache."""

import pytest

from catalyst_ai.capabilities.documents import generate
from catalyst_ai.capabilities.documents.drafting import assemble, confidence, parse, sections_of
from catalyst_ai.capabilities.documents.schema import DraftOutput
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.documents.conftest import draft_request, draft_text
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def test_run_returns_the_draft_with_every_section_cited_and_caches() -> None:
    provider = ScriptedProvider([draft_text()])
    runtime = make_runtime(provider)
    response = await generate(draft_request(), runtime, "r1")
    assert response.title == "Guide"
    assert [s.sources for s in response.sections] == [["src-runbook"], ["src-export"]]
    assert response.empty_reason is None
    assert response.confidence == 1.0
    again = await generate(draft_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_untraceable_and_uncited_sections_are_refused() -> None:
    unknown = [{"heading": "H", "text": "t", "sources": ["src-nope"]}]
    runtime = make_runtime(ScriptedProvider([draft_text(unknown)]))
    with pytest.raises(Error) as caught:
        await generate(draft_request(), runtime, "r")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "untraceable_entry"
    bare = DraftOutput.model_validate_json(
        draft_text([{"heading": "H", "text": "t", "sources": []}])
    )
    with pytest.raises(Error) as uncited:
        sections_of(bare, draft_request())
    assert uncited.value.details[0].code == "uncited_claim"


async def test_thin_sources_yield_the_reason_and_confidence_penalises() -> None:
    runtime = make_runtime(ScriptedProvider([draft_text([], "sources_insufficient")]))
    response = await generate(draft_request(), runtime, "r")
    assert response.empty_reason == "sources_insufficient"
    assert response.sections == []
    assert response.title == ""
    one = DraftOutput.model_validate_json(draft_text()).sections[:1]
    kept = sections_of(DraftOutput(sections=one, rationale="r"), draft_request())
    assert confidence(kept, draft_request()) == 0.9
    long = [{"heading": "H", "text": "word " * 200, "sources": ["src-runbook", "src-export"]}]
    kept_long = sections_of(DraftOutput.model_validate_json(draft_text(long)), draft_request())
    assert confidence(kept_long, draft_request()) == 0.8


async def test_assemble_and_the_door() -> None:
    parsed = parse(draft_request(language="ar", target_words=200), "rid", None)
    generate_request = assemble(parsed, make_runtime(ScriptedProvider([draft_text()])))
    developer = generate_request.segments[1].text
    assert "Target language: ar" in developer
    assert "About 200 words" in developer
    assert "never more than 300" in developer
    assert generate_request.segments[2].text.startswith("<<<question>>>")
    assert "[src-runbook] Incident runbook" in generate_request.segments[3].text
    off = make_runtime(
        ScriptedProvider([draft_text()]),
        make_settings(capability_documents=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await generate(draft_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    leaking = [{"heading": "H", "text": "See https://evil.example/x", "sources": ["src-runbook"]}]
    runtime = make_runtime(ScriptedProvider([draft_text(leaking)]))
    with pytest.raises(Error) as unsafe:
        await generate(draft_request(), runtime, "r")
    assert unsafe.value.code is ErrorCode.OUTPUT_UNSAFE
