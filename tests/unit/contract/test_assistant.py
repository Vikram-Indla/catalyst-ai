"""The assistant contract: the thread's rules, the context's bounds, the source shape."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.assistant import (
    MAX_TURNS,
    Context,
    TurnResponse,
    TurnSource,
)
from tests.unit.capabilities.assistant.conftest import ITEM, PAGE, turn_request


def test_defaults_and_the_last_turn_rule() -> None:
    request = turn_request()
    assert request.summary is None
    assert request.context.spaces == []
    assert request.language is None
    with pytest.raises(ValidationError, match="the member"):
        turn_request(history=[{"role": "assistant", "text": "hello"}])
    with pytest.raises(ValidationError):
        turn_request(history=[])
    too_long = [{"role": "user", "text": "x"}] * (MAX_TURNS + 1)
    with pytest.raises(ValidationError):
        turn_request(history=too_long)


@pytest.mark.parametrize(
    "context",
    [
        {"items": [{**ITEM, "id": "bad id"}]},
        {"items": [{**ITEM, "kind": "Story"}]},
        {"pages": [{**PAGE, "text": ""}]},
        {"spaces": [{"space_id": ""}]},
        {"actions": []},
    ],
    ids=["item id", "item kind", "empty page", "empty space", "unknown key"],
)
def test_malformed_context_is_refused(context: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Context.model_validate(context)


def test_the_response_carries_sources_by_marker() -> None:
    source = TurnSource(marker=2, kind="item", source_id="item-41")
    assert source.citation is None
    with pytest.raises(ValidationError):
        TurnSource(marker=0, kind="item", source_id="item-41")
    with pytest.raises(ValidationError):
        TurnSource.model_validate({"marker": 1, "kind": "link", "source_id": "x"})
    fields = set(TurnResponse.model_fields)
    assert {"reply", "sources", "not_found", "confidence"} <= fields
