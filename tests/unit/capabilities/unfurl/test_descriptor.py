"""The declaration the ledger, the gate and the runtime read."""

from catalyst_ai.capabilities.unfurl import descriptor


def test_descriptor_is_a_small_sync_capability() -> None:
    assert descriptor.kind == "sync"
    assert descriptor.retires == ("chat-unfurl",)
    assert descriptor.p95_cost_micros <= 1_000
