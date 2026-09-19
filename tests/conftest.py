"""Shared test wiring: inert settings, the app, and an in-process client; no socket ever."""

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import Environment, Settings

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_BEARER = "test-token"
SECOND_BEARER = "second-token"
TEST_DATABASE = "postgresql://test:test@localhost:5433/test"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment=Environment.DEVELOPMENT,
        service_tokens=[SecretStr(TEST_BEARER), SecretStr(SECOND_BEARER)],
        database_url=SecretStr(TEST_DATABASE),
    )


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=5.0
    ) as c:
        yield c


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_BEARER}"}
