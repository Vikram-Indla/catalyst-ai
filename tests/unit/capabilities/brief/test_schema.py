"""The model's shape: sentences with citations; extras refused; the prose gathered for scanning."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.brief.schema import ModelOutput, output_schema, prose_of, sentences_of
from tests.unit.capabilities.brief.conftest import answer


def test_the_sentences_and_notes_are_gathered_in_order() -> None:
    output = ModelOutput.model_validate_json(answer(unsupported=["no dates"]))
    assert [field for field, _ in sentences_of(output)] == ["summary", "summary", "risks", "asks"]
    assert prose_of(output).endswith("no dates")
    properties = output_schema()["properties"]
    assert isinstance(properties, dict)
    assert "summary" in properties


def test_an_extra_key_is_refused() -> None:
    with pytest.raises(ValidationError):
        ModelOutput.model_validate_json(answer(verdict="great"))
