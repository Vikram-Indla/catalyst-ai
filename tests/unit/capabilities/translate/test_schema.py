"""The output schema: what a completion must carry."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.translate.schema import ModelOutput, output_schema


def test_output_schema_names_the_fields() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert set(required) == {"translated_text", "detected_language", "rationale"}
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"translated_text": "", "detected_language": "en", "rationale": "r"}
        )
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"translated_text": "x", "detected_language": "e", "rationale": "r"}
        )
