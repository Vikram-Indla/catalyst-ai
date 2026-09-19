"""The output schema bounds the candidate list and refuses extras."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.generate_children.schema import ModelOutput, output_schema


def test_valid_and_invalid_outputs() -> None:
    ModelOutput.model_validate(
        {"candidates": [], "empty_reason": "parent_too_vague", "rationale": "r"}
    )
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"candidates": [], "empty_reason": "because", "rationale": "r"})
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"candidates": [{"type": "story", "title": "", "description": ""}], "rationale": "r"}
        )


def test_schema_lists_the_keys() -> None:
    properties = output_schema()["properties"]
    assert isinstance(properties, dict)
    assert set(properties) == {"candidates", "empty_reason", "rationale"}
