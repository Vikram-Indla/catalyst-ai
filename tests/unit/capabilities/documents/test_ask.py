"""The ask pipeline over a seeded space: passages fenced, not found without a call, the cache."""

import pytest

from catalyst_ai.capabilities.documents import ask, descriptor
from catalyst_ai.capabilities.documents.ask import assemble, parse, passages_text, retrieve_passages
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.retrieval import Passage
from tests.unit.capabilities.documents.conftest import answer_text, ask_request, seeded_runtime
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def test_run_answers_with_citations_and_caches() -> None:
    runtime = await seeded_runtime([answer_text()])
    response = await ask(ask_request(), runtime, "r1")
    assert not response.not_found
    assert response.answer == "A rollback needs the release manager's approval. [1]"
    assert [c.chunk_id for c in response.citations] == ["kb-main/doc-runbook#1"]
    assert response.citations[0].heading_path == ["Incident runbook", "Rollback"]
    assert response.citations[0].document_id == "doc-runbook"
    assert response.capability_version == descriptor.version
    again = await ask(ask_request(), runtime, "r2")
    assert again.usage.cache_hit is True


async def test_an_empty_space_is_not_found_without_a_call() -> None:
    provider = ScriptedProvider([answer_text()])
    runtime = make_runtime(provider)
    response = await ask(ask_request(space_id="empty-space"), runtime, "r")
    assert response.not_found
    assert response.answer == ""
    assert response.citations == []
    assert provider.calls == []
    seeded = await seeded_runtime([answer_text()])
    other = await ask(ask_request(space_id="other-space"), seeded, "r")
    assert other.not_found


async def test_assemble_fences_the_question_and_the_passages() -> None:
    runtime = await seeded_runtime([answer_text()])
    parsed = await retrieve_passages(parse(ask_request(language="ar"), "rid", None), runtime)
    assert parsed.retrieved is not None
    assert parsed.retrieved.passages[0].chunk_id.startswith("kb-main/")
    generate = assemble(parsed, runtime)
    assert "Target language: ar" in generate.segments[1].text
    assert 'Fill "claims"' in generate.segments[1].text
    assert generate.segments[2].text.startswith("<<<question>>>")
    assert "[kb-main/doc-runbook#" in generate.segments[3].text
    passage = Passage("kb/x#0", "x", 0, [], "text", 0.5)
    assert passages_text([passage]) == "[kb/x#0] ((none))\ntext"


async def test_the_door_refuses_switch_scanner_and_version() -> None:
    off = make_runtime(
        ScriptedProvider([answer_text()]),
        make_settings(capability_documents=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await ask(ask_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([answer_text()]))
    with pytest.raises(Error) as scanned:
        await ask(ask_request(question="mail someone@example.com"), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await ask(ask_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_an_answer_with_a_foreign_link_is_unsafe() -> None:
    claims = [{"text": "See https://evil.example/x", "chunk_ids": ["kb-main/doc-runbook#1"]}]
    runtime = await seeded_runtime([answer_text(claims)])
    with pytest.raises(Error) as caught:
        await ask(ask_request(), runtime, "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
