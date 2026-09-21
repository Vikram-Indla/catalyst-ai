"""The two output schemas and the prose the scans read."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.documents.schema import (
    AskOutput,
    DraftOutput,
    ask_prose,
    ask_schema,
    draft_prose,
    draft_schema,
)
from tests.unit.capabilities.documents.conftest import answer_text, draft_text


def test_schemas_name_the_fields_and_prose_joins_every_line() -> None:
    for schema in (ask_schema(), draft_schema()):
        required = schema["required"]
        assert isinstance(required, list)
        assert "rationale" in required
    answer = AskOutput.model_validate_json(answer_text())
    assert ask_prose(answer) == "A rollback needs the release manager's approval."
    draft = DraftOutput.model_validate_json(draft_text())
    assert draft_prose(draft).startswith("Guide\nIncidents\nAlerts page")
    with pytest.raises(ValidationError):
        AskOutput.model_validate({"claims": [], "rationale": ""})
    with pytest.raises(ValidationError):
        DraftOutput.model_validate({"rationale": "r", "extra": 1})
