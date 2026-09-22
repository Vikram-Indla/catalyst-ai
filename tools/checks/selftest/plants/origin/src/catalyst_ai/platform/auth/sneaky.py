"""A plant: the service minting a key, signing, and keeping a bearer as a fallback."""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

FALLBACK = "Bearer " + "static"


def mint() -> bytes:
    key = Ed25519PrivateKey.generate()
    return key.sign(b"anything")


def leak(settings: object) -> str:
    """A plant: a second module reading the provider's key."""
    return str(settings.provider_gemini_api_key.get_secret_value())
