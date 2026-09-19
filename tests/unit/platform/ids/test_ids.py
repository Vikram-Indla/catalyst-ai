"""UUID v7: version and variant bits, time ordering; request ids are opaque hex."""

from catalyst_ai.platform.ids import new_id, new_request_id


def test_uuid_v7_bits() -> None:
    value = new_id()
    assert value.version == 7
    assert value.variant == "specified in RFC 4122"


def test_ids_are_time_ordered() -> None:
    first, second = new_id(), new_id()
    assert first.int >> 80 <= second.int >> 80


def test_request_id_is_hex() -> None:
    rid = new_request_id()
    assert len(rid) == 16
    int(rid, 16)
