"""Grounding: an uncited sentence, a foreign id and an unseen number are refused, never dropped."""

import pytest

from catalyst_ai.capabilities.brief.postprocess import check_grounding, cited, confidence
from catalyst_ai.capabilities.brief.schema import ModelOutput
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.brief.conftest import answer, brief_request


def _output(**overrides: object) -> ModelOutput:
    return ModelOutput.model_validate_json(answer(**overrides))


def test_a_grounded_answer_passes() -> None:
    check_grounding(_output(), brief_request())
    assert ("asks", "KR-2") in cited(_output())


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"risks": [{"text": "Blocked.", "cites": []}]}, "untraceable_entry"),
        ({"risks": [{"text": "Blocked.", "cites": ["P-9"]}]}, "untraceable_entry"),
        (
            {"risks": [{"text": "It will reach 100% next month.", "cites": ["O-1"]}]},
            "unseen_number",
        ),
    ],
    ids=["no citation", "a foreign id", "an unseen number"],
)
def test_an_ungrounded_answer_is_refused(overrides: dict[str, object], code: str) -> None:
    with pytest.raises(Error) as caught:
        check_grounding(_output(**overrides), brief_request())
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert {detail.code for detail in caught.value.details} == {code}


def test_a_troubled_chain_without_a_risk_loses_confidence() -> None:
    assert confidence(_output(), brief_request()) == 1.0
    assert confidence(_output(risks=[]), brief_request()) == 0.8
