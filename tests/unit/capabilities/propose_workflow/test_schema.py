"""The output schema: what a completion must carry."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.propose_workflow.schema import ModelOutput, output_schema
from tests.unit.capabilities.propose_workflow.conftest import proposal_text


def test_output_schema_names_the_fields() -> None:
    required = output_schema()["required"]
    assert isinstance(required, list)
    assert set(required) >= {"statuses", "transitions", "rationale"}
    assert ModelOutput.model_validate_json(proposal_text()).statuses[0].key == "reported"
    with pytest.raises(ValidationError):
        ModelOutput.model_validate({"statuses": [], "transitions": [], "rationale": ""})
    with pytest.raises(ValidationError):
        ModelOutput.model_validate(
            {"statuses": [], "transitions": [], "rationale": "r", "extra": 1}
        )


def test_keys_must_be_snake_case() -> None:
    bad = proposal_text(
        statuses=[
            {
                "key": "In Work",
                "label": "x",
                "category": "todo",
                "initial": True,
                "terminal": False,
                "sort_order": 0,
            }
        ]
    )
    with pytest.raises(ValidationError):
        ModelOutput.model_validate_json(bad)
