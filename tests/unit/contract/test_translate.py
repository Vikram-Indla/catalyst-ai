"""The request model: every field classified, bounds, extras refused, the target optional."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from catalyst_ai.contract.translate import TranslateRequest
from tests.unit.capabilities.translate.conftest import make_request


def test_every_request_field_is_classified() -> None:
    properties = TranslateRequest.model_json_schema()["properties"]
    assert all(DATA_CLASS_KEY in spec for spec in properties.values())
    assert properties["text"][DATA_CLASS_KEY] == "CONFIDENTIAL"
    assert properties["target_language"][DATA_CLASS_KEY] == "PUBLIC"


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": ""},
        {"text": "x" * 20_001},
        {"context": "c" * 801},
        {"target_language": "Arabic"},
        {"mode": "comment"},
        {"unknown": 1},
    ],
    ids=["empty", "too long", "context too long", "bad tag", "unknown mode", "extra"],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_target_is_optional_in_the_model_and_refused_later() -> None:
    assert make_request(target_language=None).target_language is None
