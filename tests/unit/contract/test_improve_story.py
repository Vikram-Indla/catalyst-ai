"""The request model: every field classified, bounds enforced, extras refused."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from catalyst_ai.contract.improve_story import (
    MAX_TEXT,
    ImproveStoryMode,
    ImproveStoryRequest,
    ImproveStoryResponse,
)
from tests.unit.capabilities.improve_story.conftest import make_request


def test_every_request_field_is_classified() -> None:
    properties = ImproveStoryRequest.model_json_schema()["properties"]
    assert all(DATA_CLASS_KEY in spec for spec in properties.values())
    assert properties["description"][DATA_CLASS_KEY] == "CONFIDENTIAL"
    assert properties["mode"][DATA_CLASS_KEY] == "PUBLIC"


@pytest.mark.parametrize(
    "overrides",
    [
        {"description": "x" * (MAX_TEXT + 1)},
        {"language": "English"},
        {"mode": "rewrite"},
        {"item_type": ""},
        {"unknown": 1},
    ],
    ids=["too long", "bad language tag", "unknown mode", "empty type", "extra field"],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_modes_cover_the_previous_operations() -> None:
    assert {m.value for m in ImproveStoryMode} == {
        "clarify",
        "expand",
        "acceptance_criteria",
        "user_story",
        "shorten",
        "edge_cases",
    }


def test_response_confidence_bounds() -> None:
    with pytest.raises(ValidationError):
        ImproveStoryResponse.model_validate(
            {
                "capability_version": "1.0.0",
                "prompt_version": "1",
                "model": "m",
                "eval_set_version": "1",
                "usage": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_micros": 0,
                    "latency_ms": 0,
                    "cache_hit": False,
                },
                "request_id": "r",
                "improved_description": "d",
                "acceptance_criteria": None,
                "rationale": "r",
                "changed": False,
                "confidence": 1.5,
            }
        )
