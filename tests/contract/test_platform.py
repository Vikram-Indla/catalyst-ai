"""The platform's contract: the token, the envelope on every error, the rendered document."""

import httpx
import pytest
from fastapi import APIRouter

from catalyst_ai.app import create_app, render_openapi
from catalyst_ai.config import Settings
from catalyst_ai.contract.errors import ErrorCode, ErrorEnvelope
from catalyst_ai.platform.errors import Error
from tests.conftest import SECOND_BEARER

probe = APIRouter()


@probe.get("/probe")
async def probe_ok() -> dict[str, str]:
    return {"ok": "yes"}


@probe.get("/probe/catalog")
async def probe_catalog() -> dict[str, str]:
    raise Error(ErrorCode.BUDGET_EXCEEDED, "over", retry_after_ms=3000)


@probe.get("/probe/crash")
async def probe_crash() -> dict[str, str]:
    raise RuntimeError("boom")


@probe.get("/probe/validated/{number}")
async def probe_validated(number: int) -> dict[str, int]:
    return {"number": number}


@pytest.fixture
async def probed(settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings)
    app.include_router(probe)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=5.0)


async def test_missing_token_is_auth_token_invalid(probed: httpx.AsyncClient) -> None:
    response = await probed.get("/probe")
    assert response.status_code == 401
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.AUTH_INVALID


async def test_wrong_token_is_refused(probed: httpx.AsyncClient) -> None:
    response = await probed.get("/probe", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


async def test_second_token_is_accepted(probed: httpx.AsyncClient) -> None:
    response = await probed.get("/probe", headers={"Authorization": f"Bearer {SECOND_BEARER}"})
    assert response.status_code == 200
    assert response.json() == {"ok": "yes"}


async def test_catalog_error_renders_the_envelope(
    probed: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    response = await probed.get("/probe/catalog", headers=auth)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.BUDGET_EXCEEDED
    assert envelope.error.retry_after_ms == 3000


async def test_validation_failure_is_validation_invalid_input(
    probed: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    response = await probed.get("/probe/validated/notanumber", headers=auth)
    assert response.status_code == 400
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.VALIDATION_INVALID_INPUT
    assert envelope.error.details[0].field == "path.number"


async def test_unhandled_error_is_internal_error_without_detail(
    probed: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    response = await probed.get("/probe/crash", headers=auth)
    assert response.status_code == 500
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.INTERNAL_ERROR
    assert "boom" not in response.text


async def test_unknown_route_is_not_found(probed: httpx.AsyncClient, auth: dict[str, str]) -> None:
    response = await probed.get("/nothing", headers=auth)
    assert response.status_code == 404


def test_rendered_document_lists_every_health_operation(settings: Settings) -> None:
    document = render_openapi(create_app(settings))
    operations = {op["operationId"] for item in document["paths"].values() for op in item.values()}
    assert {"health.live", "health.ready", "improve_story.run"} <= operations
    for item in document["paths"].values():
        for operation in item.values():
            assert operation["x-capability"]
            assert "x-error-codes" in operation
