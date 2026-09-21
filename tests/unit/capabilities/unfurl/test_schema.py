"""The model's card schema: bounded facts, a rationale, nothing extra."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.unfurl.schema import ModelOutput, output_schema
from tests.unit.capabilities.unfurl.conftest import card_text


def test_schema_names_the_fields_and_refuses_extras() -> None:
    schema = output_schema()
    required = schema["required"]
    assert isinstance(required, list)
    assert set(required) == {"summary", "rationale"}
    output = ModelOutput.model_validate_json(card_text())
    assert len(output.facts) == 2
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"summary": "s", "rationale": "r", "extra": 1})
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"summary": "", "rationale": "r"})
