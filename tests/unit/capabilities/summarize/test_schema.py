"""The output schema: what a completion must carry."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.summarize.schema import ModelOutput, output_schema


def test_output_schema_names_the_fields() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert set(required) >= {"summary", "participants_mentioned", "rationale"}
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"summary": "x", "participants_mentioned": [], "rationale": ""})
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"summary": "x", "participants_mentioned": [], "rationale": "r", "extra": 1}
        )
