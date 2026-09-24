"""Shared test wiring: inert settings, the app, a signing in-process client; no socket ever."""

import tempfile
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from hypothesis import settings as hypothesis_settings
from hypothesis.configuration import set_hypothesis_home_dir
from pydantic import SecretStr

from catalyst_ai.app import create_app, default_runtime
from catalyst_ai.config import Environment, Settings
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.storage import MemoryStorage
from tools import origin
from tools.origin import SigningAuth

REPO_ROOT = Path(__file__).resolve().parent.parent
set_hypothesis_home_dir(Path(tempfile.gettempdir()) / "catalyst-ai-hypothesis")
hypothesis_settings.register_profile("repository", database=None)
hypothesis_settings.register_profile(
    "nightly",
    parent=hypothesis_settings.get_profile("repository"),
    max_examples=2000,
    deadline=None,
)
hypothesis_settings.load_profile("repository")
TEST_DATABASE = "postgresql://test:test@localhost:5433/test"
NIGHTLY_FACTOR = 20


def examples(base: int) -> int:
    """Return a property test's own example count, twenty times over under the nightly profile.

    A test pins its count because a slow parser cannot take the default; the nightly profile
    (`--hypothesis-profile=nightly`) raises every count in proportion instead of flattening them.
    """
    current = hypothesis_settings.default
    nightly = hypothesis_settings.get_profile("nightly").max_examples
    in_nightly = current is not None and current.max_examples == nightly
    return base * NIGHTLY_FACTOR if in_nightly else base


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment=Environment.DEVELOPMENT,
        auth_public_keys=origin.PUBLIC_KEYS,
        database_url=SecretStr(TEST_DATABASE),
        provider_access_token=SecretStr("developer-token"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    runtime = default_runtime(settings)
    return create_app(settings, replace(runtime, storage=MemoryStorage(runtime.clock)))


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        auth=SigningAuth(capability_of(app)),
    ) as c:
        yield c
