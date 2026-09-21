"""The request model: every field classified, the token shape, bounds, extras refused."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from catalyst_ai.contract.summarize import SummarizeRequest, ThreadItem
from tests.unit.capabilities.summarize.conftest import item, make_request


def test_every_request_field_is_classified() -> None:
    for model in (SummarizeRequest, ThreadItem):
        properties = model.model_json_schema()["properties"]
        assert all(DATA_CLASS_KEY in spec for spec in properties.values()), model.__name__
    assert ThreadItem.model_json_schema()["properties"]["text"][DATA_CLASS_KEY] == "CONFIDENTIAL"


@pytest.mark.parametrize(
    "overrides",
    [
        {"items": [item(1, "x", "Fatima")]},
        {"items": [item(1, "x", "p")]},
        {"items": [item(1, "")]},
        {"target_words": 10},
        {"target_words": 401},
        {"mode": "digest"},
        {"language": "English"},
        {"unknown": 1},
    ],
    ids=[
        "name as token",
        "bare p",
        "empty text",
        "too short",
        "too long",
        "unknown mode",
        "bad tag",
        "extra",
    ],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_defaults() -> None:
    request = make_request()
    assert request.target_words == 120
    assert request.status_changes == []
    assert request.language is None
