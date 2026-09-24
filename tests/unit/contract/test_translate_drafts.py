"""The drafts contract: one status, bounded batches, a version on every glossary."""

import typing

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.translate_drafts import MAX_ITEMS, Draft, DraftsRequest, DraftStatus
from tests.unit.capabilities.improve_story.conftest import ORG


def test_the_status_has_one_value_and_nothing_else_validates() -> None:
    assert typing.get_args(DraftStatus) == ("machine_draft",)
    assert Draft.model_json_schema()["properties"]["status"]["const"] == "machine_draft"
    with pytest.raises(ValidationError):
        Draft.model_validate(
            {"key": "0" * 64, "record_ref": "r", "field": "name", "ar": "نص", "status": "reviewed"}
        )


def test_a_batch_is_bounded_and_names_its_glossary_version() -> None:
    item = {"record_ref": "r", "field": "name", "en": "x"}
    base = {"organization_id": ORG, "capability_version": "1.2.0", "glossary_version": "g1"}
    DraftsRequest.model_validate({**base, "items": [item]})
    for bad in (
        {**base, "items": []},
        {**base, "items": [item] * (MAX_ITEMS + 1)},
        {"organization_id": ORG, "capability_version": "1.2.0", "items": [item]},
        {**base, "items": [{**item, "field": "Not A Field"}]},
    ):
        with pytest.raises(ValidationError):
            DraftsRequest.model_validate(bad)
