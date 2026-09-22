"""A plant: the service minting a key, signing, and keeping a bearer as a fallback."""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

FALLBACK = "Bearer " + "static"


def mint() -> bytes:
    key = Ed25519PrivateKey.generate()
    return key.sign(b"anything")
