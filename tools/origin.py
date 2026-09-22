"""The backend's half of the proof of origin, for tests and tooling: a signer over a fixed seed.

The service never signs (`tools/checks/origin`); the suite, the eval kit and the renderer need a
caller that does. The seed is public and fixed, so every run verifies against the same public
key; nothing here is a secret and nothing here is deployed.
"""

import base64
import secrets
from collections.abc import Generator, Mapping
from uuid import UUID

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from starlette.types import Scope

from catalyst_ai.platform.auth import Lookup, body_hash, compact, encode_claims, organization_of
from catalyst_ai.platform.auth.envelope import AUDIENCE, ISSUER
from catalyst_ai.platform.clock import Clock, SystemClock

SEED = bytes(range(32))
SECOND_SEED = bytes(reversed(range(32)))
KEY_ID = "test-1"
SECOND_KEY_ID = "test-2"
SUBJECT = "member-1"
ORG = UUID("11111111-1111-7111-8111-111111111111")
TTL_S = 30
NONCE_BYTES = 12


def _public_entry(key_id: str, key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes_raw()
    return key_id + ":" + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class Signer:
    """Sign envelopes as the backend would, with one key id."""

    def __init__(
        self, seed: bytes = SEED, key_id: str = KEY_ID, clock: Clock | None = None
    ) -> None:
        """Derive the key pair from the seed; sign against the given clock (the system's)."""
        self._key = Ed25519PrivateKey.from_private_bytes(seed)
        self.key_id = key_id
        self._clock = clock or SystemClock()

    @property
    def public_entry(self) -> str:
        """The `kid:base64url` entry the service is configured with."""
        return _public_entry(self.key_id, self._key)

    def claims(
        self, organization_id: UUID, capability: str, body: bytes, **overrides: object
    ) -> dict[str, object]:
        """Build the claims for a request; overrides let a test forge or add any field."""
        issued = int(self._clock.now().timestamp())
        claims: dict[str, object] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "org": str(organization_id),
            "cap": capability,
            "sub": SUBJECT,
            "iat": issued,
            "exp": issued + TTL_S,
            "jti": secrets.token_urlsafe(NONCE_BYTES),
            "kid": self.key_id,
            "bh": body_hash(body),
        }
        claims.update(overrides)
        return claims

    def header(self, claims: dict[str, object]) -> str:
        """Return the `Authorization` value for the claims."""
        segment = encode_claims(claims)
        return compact(segment, self._key.sign(segment))

    def sign(self, organization_id: UUID, capability: str, body: bytes, **overrides: object) -> str:
        """Claims and header in one step."""
        return self.header(self.claims(organization_id, capability, body, **overrides))


SIGNER = Signer()
SECOND_SIGNER = Signer(SECOND_SEED, SECOND_KEY_ID)
PUBLIC_KEYS = SIGNER.public_entry
BOTH_PUBLIC_KEYS = SIGNER.public_entry + "," + SECOND_SIGNER.public_entry


def unsigned(request: httpx.Request) -> httpx.Request:
    """Send the request bare; the per-request `auth` for the tests of the door itself."""
    return request


class SigningAuth(httpx.Auth):
    """An httpx auth that signs every request the way the backend will: body, tenant, route."""

    requires_request_body = True

    def __init__(
        self,
        lookup: Lookup,
        clock: Clock | None = None,
        signer: Signer | None = None,
        organization_id: UUID = ORG,
        claims: Mapping[str, object] | None = None,
        **overrides: object,
    ) -> None:
        """Hold the route lookup, the clock the app verifies against, and any forged claims."""
        self._lookup = lookup
        self._organization_id = organization_id
        self._signer = signer or Signer(clock=clock)
        self._overrides = {**(claims or {}), **overrides}

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Attach the envelope, then send."""
        query = request.url.query
        scope: Scope = {
            "type": "http",
            "method": request.method,
            "path": request.url.path,
            "root_path": "",
            "query_string": query,
        }
        capability = self._lookup(scope) or ""
        organization_id = organization_of(request.content, query) or self._organization_id
        request.headers["Authorization"] = self._signer.sign(
            organization_id, capability, request.content, **self._overrides
        )
        yield request
