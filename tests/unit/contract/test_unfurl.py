"""The unfurl contract: the kinds, the bounds, the card shape."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.unfurl import Fact, UnfurlRequest, UnfurlResponse
from tests.unit.capabilities.unfurl.conftest import unfurl_request


def test_defaults_and_kinds() -> None:
    request = unfurl_request()
    assert request.kind == "item"
    assert unfurl_request(kind="page", status=None).status is None
    with pytest.raises(ValidationError):
        unfurl_request(kind="link")
    with pytest.raises(ValidationError):
        unfurl_request(title="")
    with pytest.raises(ValidationError):
        UnfurlRequest.model_validate({**request.model_dump(mode="json"), "url": "https://x"})


def test_the_card_bounds_its_facts() -> None:
    assert Fact(label="status", value="open").label == "status"
    with pytest.raises(ValidationError):
        Fact(label="", value="open")
    fields = set(UnfurlResponse.model_fields)
    assert {"title", "summary", "facts", "confidence"} <= fields
