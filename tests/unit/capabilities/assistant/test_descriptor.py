"""The declaration the ledger, the gate and the runtime read."""

from catalyst_ai.capabilities.assistant import descriptor


def test_descriptor_names_the_stream_kind_and_what_it_retires() -> None:
    assert descriptor.kind == "stream"
    assert descriptor.name == "assistant"
    assert "caty-chat" in descriptor.retires
    assert descriptor.kill_switch == "CATALYST_AI_CAPABILITY_ASSISTANT__ENABLED"
