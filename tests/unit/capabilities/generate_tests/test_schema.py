"""The output schema: what a completion must carry, and the prose the scan reads."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.generate_tests.schema import ModelOutput, output_schema, prose_of
from tests.unit.capabilities.generate_tests.conftest import OUTLINE, TABLES, cases_text


def test_output_schema_names_the_fields_and_prose_joins_every_line() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert "rationale" in required
    output = ModelOutput.model_validate_json(cases_text(None, OUTLINE, TABLES))
    prose = prose_of(output)
    assert "Verify every column" in prose
    assert "Scope\nThe two cases" in prose
    assert "Columns\na 1" in prose
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"rationale": "r", "cases": [{"title": "x"}]})
