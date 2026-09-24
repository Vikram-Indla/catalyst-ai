"""The request model: every field classified, the two healths separate, bounds enforced."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.brief import BriefRequest, ProjectCard
from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from tests.unit.capabilities.brief.conftest import CHAIN, brief_request


def _classified(schema: dict[str, object]) -> bool:
    properties = schema.get("properties", {})
    return isinstance(properties, dict) and all(DATA_CLASS_KEY in s for s in properties.values())


def test_every_request_field_is_classified_at_every_level() -> None:
    schema = BriefRequest.model_json_schema()
    definitions = schema["$defs"]
    assert _classified(schema)
    for name in ("KeyResult", "Objective", "ProjectCard", "Finding", "Theme"):
        assert _classified(definitions[name]), name


def test_delivery_and_strategic_health_are_two_required_fields() -> None:
    fields = ProjectCard.model_fields
    assert fields["delivery_health"].is_required()
    assert fields["strategic_health"].is_required()


@pytest.mark.parametrize(
    "overrides",
    [
        {"locale": "fr"},
        {"max_sentences": 6},
        {"audience": "everyone"},
        {"chain": {**CHAIN, "theme": {"id": "bad id!", "title": "t"}}},
        {"unknown": 1},
    ],
    ids=["locale", "too long", "audience", "id shape", "extra field"],
)
def test_invalid_requests(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        brief_request(**overrides)
