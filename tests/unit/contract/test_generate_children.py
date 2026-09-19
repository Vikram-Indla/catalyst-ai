"""The request model: every field classified, hierarchy bounds, extras refused."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from catalyst_ai.contract.generate_children import GenerateChildrenRequest, GenerateTarget
from tests.unit.capabilities.generate_children.conftest import make_request


def test_every_request_field_is_classified() -> None:
    properties = GenerateChildrenRequest.model_json_schema()["properties"]
    assert all(DATA_CLASS_KEY in spec for spec in properties.values())
    assert properties["parent_description"][DATA_CLASS_KEY] == "CONFIDENTIAL"
    assert properties["hierarchy"][DATA_CLASS_KEY] == "INTERNAL"


@pytest.mark.parametrize(
    "overrides",
    [
        {"hierarchy": ["one"]},
        {"max_items": 0},
        {"max_items": 21},
        {"target": "tasks"},
        {"siblings": [{"title": ""}]},
        {"unknown": 1},
    ],
    ids=[
        "one level",
        "zero items",
        "too many items",
        "unknown target",
        "empty sibling",
        "extra field",
    ],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_targets() -> None:
    assert {t.value for t in GenerateTarget} == {"stories", "epics", "children"}
    assert make_request().max_items == 7
