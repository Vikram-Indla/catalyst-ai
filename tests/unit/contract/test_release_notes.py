"""The release-notes contract: the request's rules and the shapes."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.release_notes import Audience, ReleaseNotesMode, StatusCategory
from tests.unit.capabilities.release_notes.conftest import CHANGES, make_request


def test_defaults_and_enums() -> None:
    request = make_request()
    assert request.mode is ReleaseNotesMode.NOTES
    assert request.audience is Audience.INTERNAL
    assert request.changes[2].status_category is StatusCategory.IN_PROGRESS
    assert request.language is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "digest"},
        {"changes": [{**CHANGES[0], "kind": "Story"}]},
        {"changes": [{**CHANGES[0], "participant": "Fatima"}]},
        {"changes": [{**CHANGES[0], "title": ""}]},
        {"release": {"name": ""}},
        {"language": "English"},
    ],
)
def test_malformed_requests_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)
