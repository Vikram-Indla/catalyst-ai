"""The provider's token: the runtime's workload identity, or a developer's own short-lived token.

A deployed process authenticates to the regional provider as its own identity: the metadata
server beside it issues a short-lived access token for the service account the workload runs as,
and nothing long-lived is configured anywhere. In development a developer may set their own
short-lived token (`PROVIDER_ACCESS_TOKEN`, from their own login); the settings refuse it outside
development. This is the one module that forms the provider's authorization header: the service
still holds no credential of the backend's, and never presents one to it.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import httpx

from catalyst_ai.config import Settings
from catalyst_ai.platform.clock import Clock

METADATA_ENDPOINT = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
)
METADATA_HEADERS = MappingProxyType({"Metadata-Flavor": "Google"})
METADATA_TIMEOUT_S = 5.0
REFRESH_EARLY = timedelta(seconds=60)


@dataclass(frozen=True)
class DeveloperToken:
    """A developer's own short-lived token, as set in their environment; development only."""

    value: str

    async def token(self) -> str:
        """Return the token as set; it expires when the developer's login does."""
        return self.value

    async def ready(self) -> bool:
        """Return True: a developer's token cannot be checked without a call."""
        return True


@dataclass
class WorkloadIdentity:
    """The runtime's own identity, through the metadata server; refreshed before it expires."""

    client: httpx.AsyncClient
    clock: Clock
    cached: str = ""
    expires: datetime = field(default_factory=lambda: datetime.min.replace(tzinfo=UTC))

    async def token(self) -> str:
        """Return the cached token, or a fresh one when it is within a minute of expiring."""
        now = self.clock.now()
        if self.cached and now < self.expires - REFRESH_EARLY:
            return self.cached
        response = await self.client.get(
            METADATA_ENDPOINT, headers=dict(METADATA_HEADERS), timeout=METADATA_TIMEOUT_S
        )
        response.raise_for_status()
        issued = response.json()
        self.cached = str(issued["access_token"])
        self.expires = now + timedelta(seconds=int(issued["expires_in"]))
        return self.cached

    async def ready(self) -> bool:
        """Return whether a token is held and unexpired; a failed refresh before expiry stays ready.

        Red until the metadata server has issued the first token, so a rollout on a node without
        the workload identity (or with the metadata server blocked) never takes traffic; red again
        only once the held token has expired and no refresh succeeded.
        """
        try:
            await self.token()
        except (httpx.HTTPError, KeyError, ValueError):
            return bool(self.cached) and self.clock.now() < self.expires
        return True


type TokenSource = DeveloperToken | WorkloadIdentity


def token_source(settings: Settings, client: httpx.AsyncClient, clock: Clock) -> TokenSource:
    """Return the developer's token when one is set (development only), else the workload's."""
    developer = settings.provider_access_token
    if developer is not None:
        return DeveloperToken(developer.get_secret_value())
    return WorkloadIdentity(client, clock)


async def authorization(source: TokenSource) -> dict[str, str]:
    """Return the provider's authorization header for the current token."""
    return {"Authorization": f"Bearer {await source.token()}"}
