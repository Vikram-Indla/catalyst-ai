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
