"""UUID v7 from the standard library's primitives; the only place an id is minted."""

import secrets
import time
from uuid import UUID

UNIX_MS_BITS = 48
RAND_A_BITS = 12
RAND_B_BITS = 62
VERSION_7 = 7
VARIANT_RFC = 0b10
REQUEST_ID_BYTES = 8


def new_id() -> UUID:
    """Mint a UUID v7: 48 bits of milliseconds, then random bits, version and variant set."""
    unix_ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(RAND_A_BITS)
    rand_b = secrets.randbits(RAND_B_BITS)
    value = (unix_ms << (128 - UNIX_MS_BITS)) | (VERSION_7 << 76) | (rand_a << 64)
    value |= (VARIANT_RFC << 62) | rand_b
    return UUID(int=value)


def new_request_id() -> str:
    """Mint an opaque request id for logs and envelopes."""
    return secrets.token_hex(REQUEST_ID_BYTES)
