"""Cache keys: every component changes the key; organisations never collide."""

from uuid import uuid4

from catalyst_ai.platform.cache import cache_key, idempotency_key

VERSIONS = ("1.0.0", "1", "text-default")


def test_same_input_same_key() -> None:
    org = uuid4()
    assert cache_key(org, "c", VERSIONS, {"a": 1}) == cache_key(org, "c", VERSIONS, {"a": 1})


def test_every_component_changes_the_key() -> None:
    org = uuid4()
    base = cache_key(org, "c", VERSIONS, {"a": 1})
    assert cache_key(uuid4(), "c", VERSIONS, {"a": 1}) != base
    assert cache_key(org, "d", VERSIONS, {"a": 1}) != base
    assert cache_key(org, "c", ("2.0.0", "1", "text-default"), {"a": 1}) != base
    assert cache_key(org, "c", ("1.0.0", "2", "text-default"), {"a": 1}) != base
    assert cache_key(org, "c", ("1.0.0", "1", "text-fast"), {"a": 1}) != base
    assert cache_key(org, "c", VERSIONS, {"a": 2}) != base


def test_idempotency_key_scoped_by_organisation() -> None:
    header = "abc"
    assert idempotency_key(uuid4(), "c", header) != idempotency_key(uuid4(), "c", header)
