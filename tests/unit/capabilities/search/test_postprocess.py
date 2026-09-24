"""The response builders carry the descriptor's versions and log the usage row only when spent."""

import logging

import pytest

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.capabilities.search.postprocess import (
    to_delete_response,
    to_response,
    to_upsert_response,
)
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.search import Hit, Provenance
from catalyst_ai.retrieval import Found, UpsertOutcome
from catalyst_ai.retrieval.embeddings import NO_USAGE
from catalyst_ai.retrieval.ingest import IndexedOutcome
from tests.unit.capabilities.improve_story.conftest import ORG
from tests.unit.capabilities.search.conftest import search_request

SPENT = Usage(input_tokens=5, output_tokens=0, cost_micros=1, latency_ms=2, cache_hit=False)


def test_search_response_logs_a_row_only_when_the_port_was_called(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="catalyst_ai.provider_calls"):
        free = to_response(Found([], NO_USAGE, "m", "v", consulted=False), search_request(), "r")
        assert free.usage == NO_USAGE
        assert not caplog.records
        paid = to_response(Found([], SPENT, "m", "v"), search_request(), "r")
    assert paid.model == f"{descriptor.alias}@m"
    assert paid.usage == SPENT
    assert len(caplog.records) == 1
    assert caplog.records[0].__dict__["capability"] == descriptor.name


def test_upsert_and_delete_responses() -> None:
    outcome = UpsertOutcome([IndexedOutcome("A-1", 2, "m", "v", unchanged=False)], 2, SPENT, "m")
    upserted = to_upsert_response(outcome, ORG, "r")
    assert upserted.results[0].chunks == 2
    assert upserted.index_chunks == 2
    assert upserted.eval_set_version == descriptor.eval_set_version
    deleted = to_delete_response(3, "m", "r")
    assert deleted.deleted_chunks == 3
    assert deleted.usage == NO_USAGE
    assert deleted.prompt_version == descriptor.prompt_version


def test_ids_only_returns_keys_kinds_and_scores_without_content() -> None:
    provenance = Provenance(chunk_index=0, embedding_model="m", embedding_version="v")
    hit = Hit(
        external_id="KR-7",
        kind="record",
        title="A private title",
        score=0.8,
        snippet="private text",
        provenance=provenance,
    )
    found = Found([hit], SPENT, "m", "v")
    bare = to_response(found, search_request(ids_only=True), "r").hits[0]
    assert (bare.external_id, bare.kind, bare.score) == ("KR-7", "record", 0.8)
    assert bare.title is None
    assert bare.snippet == ""
    full = to_response(found, search_request(), "r").hits[0]
    assert full.title == "A private title"
