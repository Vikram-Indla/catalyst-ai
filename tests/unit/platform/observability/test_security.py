"""Security events: counted by event and reason, logged with ids only."""

import logging

import pytest

from catalyst_ai.platform.observability import (
    JOB_QUARANTINED,
    ORIGIN_REFUSED,
    SecurityCounters,
    Where,
    security_event,
)


def test_counters_sum_over_reasons_and_start_at_zero() -> None:
    counters = SecurityCounters()
    assert counters.value(ORIGIN_REFUSED) == 0
    counters.count(ORIGIN_REFUSED, "expired")
    counters.count(ORIGIN_REFUSED, "expired")
    counters.count(ORIGIN_REFUSED, "replayed")
    counters.count(JOB_QUARANTINED, "malformed")
    assert counters.value(ORIGIN_REFUSED, "expired") == 2
    assert counters.value(ORIGIN_REFUSED) == 3
    assert counters.value(JOB_QUARANTINED) == 1
    assert counters.value(JOB_QUARANTINED, "expired") == 0


def test_an_event_is_logged_with_its_reason_and_ids_and_counted(
    caplog: pytest.LogCaptureFixture,
) -> None:
    counters = SecurityCounters()
    where = Where("req-1", capability="summarize", key_id="k1")
    with caplog.at_level(logging.WARNING, logger="catalyst_ai.security"):
        security_event(counters, ORIGIN_REFUSED, "bad_signature", where)
    record = caplog.records[-1]
    assert record.getMessage() == ORIGIN_REFUSED
    assert vars(record)["reason"] == "bad_signature"
    assert vars(record)["request_id"] == "req-1"
    assert vars(record)["capability"] == "summarize"
    assert vars(record)["key_id"] == "k1"
    assert counters.value(ORIGIN_REFUSED, "bad_signature") == 1
