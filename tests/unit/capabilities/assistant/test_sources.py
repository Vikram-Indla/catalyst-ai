"""Sources numbered for the prompt; markers resolved; uncited facts and unknown numbers refused."""

import pytest

from catalyst_ai.capabilities.assistant.sources import (
    check_reply,
    markers_of,
    number_sources,
    sources_cited,
    sources_text,
)
from catalyst_ai.contract.assistant import Context
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.retrieval import Passage
from tests.unit.capabilities.assistant.conftest import ITEM, PAGE

PASSAGE = Passage("kb-main/doc-runbook#1", "doc-runbook", 1, ["Runbook", "Rollback"], "A.", 0.8)
CONTEXT = Context.model_validate({"items": [ITEM], "pages": [PAGE]})


def test_sources_are_numbered_passages_then_items_then_pages() -> None:
    sources = number_sources([PASSAGE], CONTEXT)
    assert [(s.number, s.kind, s.source_id) for s in sources] == [
        (1, "passage", "kb-main/doc-runbook#1"),
        (2, "item", "item-41"),
        (3, "page", "page-9"),
    ]
    text = sources_text(sources)
    assert text.startswith("[1] (Runbook > Rollback)\nA.")
    assert "[2] story APP-41: Login button broken on mobile\nstatus: in_progress\nThe login" in text
    assert "[3] page page-9: Release checklist\nEvery release" in text
    assert sources_text([]) == ""


def test_markers_and_citations_resolve_in_order_of_first_use() -> None:
    sources = number_sources([PASSAGE], CONTEXT)
    reply = "Approval is needed. [1] The button is broken. [2][1] The checklist says so. [3]"
    assert markers_of(reply) == [1, 2, 3]
    cited = sources_cited(reply, sources)
    assert [(s.marker, s.kind, s.source_id) for s in cited] == [
        (1, "passage", "kb-main/doc-runbook#1"),
        (2, "item", "item-41"),
        (3, "page", "page-9"),
    ]
    assert cited[0].citation is not None
    assert cited[0].citation.heading_path == ["Runbook", "Rollback"]
    assert cited[1].citation is None
    assert sources_cited("no markers", sources) == []


def test_check_reply_refuses_unknown_numbers_and_uncited_facts() -> None:
    sources = number_sources([PASSAGE], CONTEXT)
    with pytest.raises(Error) as unknown:
        check_reply("The rota changes on Sunday. [7]", sources, not_found=False)
    assert unknown.value.code is ErrorCode.OUTPUT_INVALID
    assert unknown.value.details[0].code == "untraceable_entry"
    assert unknown.value.details[0].message == "7"
    with pytest.raises(Error) as uncited:
        check_reply(
            "The rota changes every Sunday at nine in the morning.", sources, not_found=False
        )
    assert uncited.value.details[0].code == "uncited_claim"
    check_reply(
        "Sure. Is this about the runbook? The rota changes every Sunday. [1]",
        sources,
        not_found=False,
    )
    check_reply("I could not find that in the sources you gave me here.", sources, not_found=True)
    check_reply("Anything at all goes when there are no sources to cite.", [], not_found=False)
