"""The retrieval models: classification, bounds, the hash pattern, extras refused."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import DATA_CLASS_KEY
from catalyst_ai.contract.search import (
    IndexDeleteRequest,
    IndexDocument,
    IndexUpsertRequest,
    SearchRequest,
)
from tests.unit.capabilities.search.conftest import (
    delete_request,
    document,
    search_request,
    upsert_request,
)


def test_every_request_field_is_classified() -> None:
    for model in (IndexUpsertRequest, IndexDeleteRequest, SearchRequest, IndexDocument):
        properties = model.model_json_schema()["properties"]
        assert all(DATA_CLASS_KEY in spec for spec in properties.values()), model.__name__
    assert IndexDocument.model_json_schema()["properties"]["text"][DATA_CLASS_KEY] == "CONFIDENTIAL"
    assert SearchRequest.model_json_schema()["properties"]["k"][DATA_CLASS_KEY] == "PUBLIC"


@pytest.mark.parametrize(
    "build",
    [
        lambda: upsert_request(documents=[]),
        lambda: upsert_request(document("A-1", "t", content_hash="abc")),
        lambda: upsert_request(document("A-1", "t", data_class="RESTRICTED")),
        lambda: upsert_request(document("A-1", "t", kind="Story")),
        lambda: upsert_request(corpus="pages"),
        lambda: delete_request(external_ids=[]),
        lambda: search_request(k=0),
        lambda: search_request(k=51),
        lambda: search_request(mode="fuzzy"),
        lambda: search_request(""),
        lambda: search_request(unknown=1),
    ],
    ids=[
        "no documents",
        "bad hash",
        "restricted class",
        "kind not lower snake",
        "unknown corpus",
        "no keys",
        "k zero",
        "k over",
        "unknown mode",
        "empty text",
        "extra field",
    ],
)
def test_invalid_requests(build: Callable[[], object]) -> None:
    with pytest.raises(ValidationError):
        build()


def test_defaults() -> None:
    request = search_request()
    assert request.k == 10
    assert request.kinds == []
    assert request.exclude_external_ids == []
