"""The post-mortem contract: tokens as a schema rule, facts apart from analysis."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.post_mortem import Factor
from tests.unit.capabilities.post_mortem.conftest import TIMELINE, make_request


def test_defaults() -> None:
    request = make_request()
    assert request.timeline[3].participant is None
    assert request.incident.started_at is None
    assert request.language is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"timeline": [{**TIMELINE[0], "participant": "Fatima Al-Sayed"}]},
        {"timeline": [{**TIMELINE[0], "participant": "p10000"}]},
        {"timeline": [{**TIMELINE[0], "id": ""}]},
        {"incident": {"title": ""}},
        {"language": "English"},
    ],
)
def test_malformed_requests_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_a_factor_needs_evidence() -> None:
    with pytest.raises(ValidationError):
        Factor(text="x", evidence=[])
