"""The output schema: what a completion must carry, and the prose the scan reads."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.release_notes.schema import ModelOutput, output_schema, prose_of
from tests.unit.capabilities.release_notes.conftest import notes_text


def test_output_schema_names_the_fields_and_prose_joins_every_line() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert "rationale" in required
    output = ModelOutput.model_validate_json(notes_text(summary="lead"))
    prose = prose_of(output)
    assert prose.startswith("lead\n")
    assert "PRJ-101: export the board (p1)" in prose
    assert "Export the board" in prose
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"rationale": ""})
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"rationale": "r", "extra": 1})
