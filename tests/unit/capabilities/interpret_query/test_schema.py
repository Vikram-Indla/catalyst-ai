"""The model's output: a query, an explanation, the terms it left out, a rationale."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.interpret_query.schema import ModelOutput, output_schema


def test_the_unresolved_terms_are_trimmed_and_blank_ones_dropped() -> None:
    output = ModelOutput(query="", explanation="x", unresolved=["  red ", "", " "], rationale="r")
    assert output.terms() == ["red"]


def test_an_explanation_and_a_rationale_are_required() -> None:
    with pytest.raises(ValidationError):
        ModelOutput(query="", explanation="", unresolved=[], rationale="r")
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"query": "", "explanation": "x", "rationale": "r", "sql": "x"})


def test_the_provider_gets_the_schema_it_must_answer_in() -> None:
    schema = output_schema()
    required, properties = schema["required"], schema["properties"]
    assert isinstance(required, list)
    assert isinstance(properties, dict)
    assert set(required) >= {"explanation", "rationale"}
    assert {"query", "parameters", "sort"} <= set(properties)
