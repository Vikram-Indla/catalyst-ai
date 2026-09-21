"""The documents contracts: one content, the id shapes, the enums, the shapes."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.documents import Citation, DocumentFormat, DraftSection, Source
from tests.unit.capabilities.documents.conftest import ask_request, draft_request, ingest_request


def test_defaults_and_enums() -> None:
    assert ingest_request().format is DocumentFormat.MARKDOWN
    assert ask_request().kinds == []
    assert ask_request().k == 4
    assert draft_request().target_words == 100


@pytest.mark.parametrize(
    "overrides",
    [
        {"text": None},
        {"content_base64": "eA==", "text": "x"},
        {"space_id": "bad space"},
        {"document_id": "/etc/passwd"},
        {"kind": "Wiki"},
        {"format": "xlsx"},
        {"content_hash": "abc"},
        {"data_class": "RESTRICTED"},
    ],
)
def test_malformed_ingest_requests_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ingest_request(**overrides)


def test_ask_and_draft_shapes() -> None:
    with pytest.raises(ValidationError):
        ask_request(k=0)
    with pytest.raises(ValidationError):
        ask_request(question="")
    with pytest.raises(ValidationError):
        draft_request(sources=[])
    with pytest.raises(ValidationError):
        draft_request(target_words=50)
    with pytest.raises(ValidationError):
        Source(id="a b", text="t")
    with pytest.raises(ValidationError):
        DraftSection(heading="h", text="t", sources=[])
    with pytest.raises(ValidationError):
        Citation(chunk_id="c", document_id="d", position=0, heading_path=[], quote="q" * 301)
