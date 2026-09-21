"""The generate-tests contract: the request's rules and the shapes."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.generate_tests import DataTable, GenerateTestsMode
from tests.unit.capabilities.generate_tests.conftest import CRITERIA, make_request


def test_defaults_and_enums() -> None:
    request = make_request()
    assert request.mode is GenerateTestsMode.CASES
    assert request.cases == []
    assert make_request(max_cases=10).max_cases == 10


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "plan"},
        {"max_cases": 0},
        {"max_cases": 21},
        {"criteria": [{**CRITERIA[0], "id": ""}]},
        {"story": {"title": ""}},
        {"language": "English"},
    ],
)
def test_malformed_requests_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_a_table_needs_a_column_and_a_citation() -> None:
    with pytest.raises(ValidationError):
        DataTable(name="x", columns=[], rows=[], covers=["tc-1"])
    with pytest.raises(ValidationError):
        DataTable(name="x", columns=["a"], rows=[], covers=[])
