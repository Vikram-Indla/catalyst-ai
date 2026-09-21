"""Stage 7 of ask: uncited and untraceable claims refused, citations laid out, confidence, cache."""

import pytest

from catalyst_ai.capabilities.documents.citations import (
    check_claims,
    citations_of,
    confidence,
    from_cache,
    not_found_response,
    quote_for,
    render_answer,
    to_response,
)
from catalyst_ai.capabilities.documents.schema import AskOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from catalyst_ai.retrieval import Passage, Retrieved
from tests.unit.capabilities.documents.conftest import answer_text, ask_request

USAGE = Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False)
RESULT = GenerateResult(text="", model_id="double", usage=USAGE)
PASSAGES = [
    Passage(
        "kb-main/doc-runbook#1",
        "doc-runbook",
        1,
        ["Runbook", "Rollback"],
        "A rollback needs approval. " * 20,
        0.8,
    ),
    Passage(
        "kb-main/doc-runbook#0",
        "doc-runbook",
        0,
        ["Runbook", "Paging"],
        "Alerts page the on-call engineer.",
        0.3,
    ),
]
RETRIEVED = Retrieved(PASSAGES, USAGE, "double")


def _output(claims: list[dict[str, object]], *, not_found: bool = False) -> AskOutput:
    return AskOutput.model_validate_json(answer_text(claims, not_found=not_found))


def test_to_response_cites_every_claim_with_markers() -> None:
    output = _output(
        [
            {"text": "Approval is needed.", "chunk_ids": ["kb-main/doc-runbook#1"]},
            {
                "text": "Alerts page on-call.",
                "chunk_ids": ["kb-main/doc-runbook#0", "kb-main/doc-runbook#1"],
            },
        ]
    )
    response = to_response(output, RESULT, RETRIEVED, ask_request(), "rid")
    assert response.answer == "Approval is needed. [1] Alerts page on-call. [2][1]"
    assert [c.chunk_id for c in response.citations] == [
        "kb-main/doc-runbook#1",
        "kb-main/doc-runbook#0",
    ]
    assert len(response.citations[0].quote) <= 300
    assert response.citations[0].quote.startswith("A rollback needs approval.")
    assert response.confidence == 1.0
    assert not response.not_found


def test_uncited_and_untraceable_claims_are_refused() -> None:
    with pytest.raises(Error) as uncited:
        check_claims(_output([{"text": "Guess.", "chunk_ids": []}]), PASSAGES)
    assert uncited.value.code is ErrorCode.OUTPUT_INVALID
    assert uncited.value.details[0].code == "uncited_claim"
    with pytest.raises(Error) as unknown:
        check_claims(_output([{"text": "Made up.", "chunk_ids": ["kb-main/doc-x#9"]}]), PASSAGES)
    assert unknown.value.details[0].code == "untraceable_entry"
    assert unknown.value.details[0].message == "kb-main/doc-x#9"


def test_not_found_and_empty_claims() -> None:
    plain = not_found_response(RETRIEVED, "rid")
    assert plain.not_found
    assert plain.answer == ""
    assert plain.citations == []
    assert plain.usage == USAGE
    said = to_response(_output([], not_found=True), RESULT, RETRIEVED, ask_request(), "rid")
    assert said.not_found
    blank = to_response(
        _output([{"text": "  ", "chunk_ids": []}]), RESULT, RETRIEVED, ask_request(), "rid"
    )
    assert blank.not_found


def test_confidence_quote_and_cache() -> None:
    weak = _output([{"text": "x", "chunk_ids": ["kb-main/doc-runbook#0"]}])
    assert confidence(weak, RETRIEVED) == 0.7
    strong = _output(
        [
            {"text": "x", "chunk_ids": ["kb-main/doc-runbook#1"]},
            {"text": "y", "chunk_ids": ["kb-main/doc-runbook#1"]},
        ]
    )
    assert confidence(strong, RETRIEVED) == 1.0
    assert quote_for(PASSAGES[1], "claim") == "Alerts page the on-call engineer."
    assert len(quote_for(PASSAGES[0], "claim")) <= 300
    assert render_answer([], []) == ""
    assert citations_of(_output([]), PASSAGES) == []
    response = to_response(strong, RESULT, RETRIEVED, ask_request(), "r1")
    again = from_cache(response.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
