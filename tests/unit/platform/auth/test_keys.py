"""The key registry: one or two public keys by id; a verify that answers for them only."""

import base64

import pytest

from catalyst_ai.platform.auth import KeyRegistry, PublicKeyConfigError
from tools import origin


def test_a_registry_loads_one_or_two_keys_and_verifies_with_them_only() -> None:
    both = KeyRegistry.from_config(origin.BOTH_PUBLIC_KEYS)
    assert both.key_ids == frozenset({origin.KEY_ID, origin.SECOND_KEY_ID})
    assert both.verify("nobody", b"x", bytes(64)) is False
    assert both.verify(origin.KEY_ID, b"x", bytes(64)) is False
    with pytest.raises(PublicKeyConfigError):
        KeyRegistry.from_config("")
    with pytest.raises(PublicKeyConfigError):
        KeyRegistry.from_config(origin.PUBLIC_KEYS + "," + origin.PUBLIC_KEYS)
    arbitrary = "k1:" + base64.urlsafe_b64encode(bytes([255] * 32)).rstrip(b"=").decode()
    assert KeyRegistry.from_config(arbitrary).verify("k1", b"x", bytes(64)) is False
