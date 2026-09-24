"""The provider's token: a developer's as set, the workload's cached until a minute before expiry."""

from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr

from catalyst_ai.config import Environment, Settings
from catalyst_ai.providers.gemini.credentials import (
    METADATA_ENDPOINT,
    DeveloperToken,
    WorkloadIdentity,
    authorization,
    token_source,
)
from tools import origin


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 24, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


class MetadataServer:
    def __init__(self) -> None:
        self.calls = 0
        self.headers: list[httpx.Headers] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        self.headers.append(request.headers)
        assert str(request.url) == METADATA_ENDPOINT
        return httpx.Response(
            200, json={"access_token": f"workload-{self.calls}", "expires_in": 3600}
        )


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "auth_public_keys": origin.PUBLIC_KEYS,
        "database_url": SecretStr("postgresql://u:p@h/d"),
    }
    values.update(overrides)
    return Settings.model_validate(values)


async def test_a_developer_token_is_used_as_set() -> None:
    server = MetadataServer()
    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as client:
        source = token_source(
            _settings(provider_access_token=SecretStr("mine")), client, FrozenClock()
        )
    assert isinstance(source, DeveloperToken)
    assert await authorization(source) == {"Authorization": "Bearer mine"}
    assert server.calls == 0


async def test_the_workload_token_is_cached_and_refreshed_before_it_expires() -> None:
    server = MetadataServer()
    clock = FrozenClock()
    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as client:
        source = token_source(_settings(), client, clock)
        assert isinstance(source, WorkloadIdentity)
        assert await source.token() == "workload-1"
        clock.at += timedelta(seconds=3600 - 61)
        assert await source.token() == "workload-1"
        clock.at += timedelta(seconds=2)
        assert await source.token() == "workload-2"
    assert server.calls == 2
    assert server.headers[0]["metadata-flavor"] == "Google"


class FlakyMetadata(MetadataServer):
    def __init__(self) -> None:
        super().__init__()
        self.down = True

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            return httpx.Response(503)
        return super().__call__(request)


async def test_ready_waits_for_the_first_token_and_outlives_a_failed_refresh_until_expiry() -> None:
    server = FlakyMetadata()
    clock = FrozenClock()
    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as client:
        source = WorkloadIdentity(client, clock)
        assert await source.ready() is False
        server.down = False
        assert await source.ready() is True
        server.down = True
        clock.at += timedelta(seconds=3600 - 30)
        assert await source.ready() is True
        clock.at += timedelta(seconds=31)
        assert await source.ready() is False


async def test_a_developer_token_is_ready() -> None:
    assert await DeveloperToken("mine").ready() is True
