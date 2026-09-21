"""Shared test wiring: inert settings, the app, and an in-process client; no socket ever."""

import tempfile
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from hypothesis import settings as hypothesis_settings
from hypothesis.configuration import set_hypothesis_home_dir
from pydantic import SecretStr

from catalyst_ai.app import create_app, default_runtime
from catalyst_ai.config import Environment, Settings
from catalyst_ai.platform.storage import MemoryStorage

REPO_ROOT = Path(__file__).resolve().parent.parent
set_hypothesis_home_dir(Path(tempfile.gettempdir()) / "catalyst-ai-hypothesis")
hypothesis_settings.register_profile("repository", database=None)
hypothesis_settings.load_profile("repository")
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
    runtime = default_runtime(settings)
    app = create_app(settings, replace(runtime, storage=MemoryStorage(runtime.clock)))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=5.0
    ) as c:
        yield c


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TEST_BEARER}"}
