"""The output schema: what a completion must carry, and the prose the scans read."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.post_mortem.schema import ModelOutput, output_schema, prose_of
from tests.unit.capabilities.post_mortem.conftest import draft_text


def test_output_schema_names_the_fields_and_prose_joins_every_line() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert "rationale" in required
    output = ModelOutput.model_validate_json(draft_text())
    prose = prose_of(output)
    assert prose.startswith("The search endpoint failed")
    assert "A deploy preceded the failure" in prose
    assert "Add a canary step" in prose
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"rationale": "r", "action_items": [{"text": "x", "confidence": 2}]}
        )
