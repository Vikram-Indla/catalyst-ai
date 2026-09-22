"""The public keys the service verifies with, by key id; it holds no private key, ever.

Configuration carries `kid:base64url(32 raw bytes)` entries separated by commas — two during a
rotation, one otherwise (parsed by the settings). The only cryptographic primitive in this
repository is the verify call below; a signing primitive anywhere in `src/` is a gate violation
(`tools/checks/origin`).
"""

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from catalyst_ai.config import PublicKeyEntry, parse_public_keys


class PublicKeyConfigError(ValueError):
    """The configured public keys are not one or two `kid:base64url` entries of 32 bytes."""


class KeyRegistry:
    """The active public keys; `verify` says whether a signature is theirs."""

    def __init__(self, entries: list[PublicKeyEntry]) -> None:
        """Load the configured entries; bytes that are no point verify nothing, which is safe."""
        self._keys = {
            entry.key_id: Ed25519PublicKey.from_public_bytes(entry.raw) for entry in entries
        }

    @classmethod
    def from_config(cls, text: str) -> "KeyRegistry":
        """Parse the configuration string (validated by the settings) into a registry."""
        try:
            return cls(parse_public_keys(text))
        except ValueError as error:
            raise PublicKeyConfigError(str(error)) from error

    @property
    def key_ids(self) -> frozenset[str]:
        """The ids the registry can verify with."""
        return frozenset(self._keys)

    def verify(self, key_id: str, signed: bytes, signature: bytes) -> bool:
        """Return whether `signature` is the named key's signature over `signed`."""
        key = self._keys.get(key_id)
        if key is None:
            return False
        try:
            key.verify(signature, signed)
        except InvalidSignature:
            return False
        return True
