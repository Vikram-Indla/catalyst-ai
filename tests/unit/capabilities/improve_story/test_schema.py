"""The output schema forbids extras and bounds every text."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.improve_story.schema import ModelOutput, output_schema


def test_valid_output() -> None:
    output = ModelOutput(description="d", acceptance_criteria=None, rationale="why", changed=True)
    assert output.changed is True


@pytest.mark.parametrize(
    "payload",
    [
        {"description": "d", "rationale": "", "changed": True},
        {"description": "d", "rationale": "r", "changed": True, "extra": 1},
        {"description": "d", "changed": True},
    ],
    ids=["empty rationale", "extra key", "missing rationale"],
)
def test_invalid_outputs(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(payload)


def test_schema_lists_the_four_keys() -> None:
    properties = output_schema()["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == {
        "description",
        "acceptance_criteria",
        "rationale",
        "changed",
    }
