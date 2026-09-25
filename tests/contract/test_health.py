"""health.live and health.ready through the app: shape, exemption from auth, request id."""

from dataclasses import replace

import httpx
from fastapi import FastAPI

from catalyst_ai.app import create_app
from catalyst_ai.contract.health import LiveResponse, ReadyResponse
from catalyst_ai.platform.httpserver import REQUEST_ID_HEADER
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


async def _no_identity() -> bool:
    return False


async def test_health_live_returns_live_without_a_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert LiveResponse.model_validate(response.json()).status == "live"
    assert len(response.headers[REQUEST_ID_HEADER]) == 16


async def test_health_ready_returns_ready_with_checks(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    ready = ReadyResponse.model_validate(response.json())
    assert ready.status == "ready"
    assert ready.checks == {
        "settings": True,
        "storage": True,
        "provider_credentials": True,
        "serving": True,
    }


async def test_health_ready_turns_false_while_the_process_drains(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    app.state.draining = True
    response = await client.get("/readyz")
    ready = ReadyResponse.model_validate(response.json())
    assert ready.status == "not_ready"
    assert ready.checks["serving"] is False
    app.state.draining = False


async def test_health_live_echoes_a_supplied_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={REQUEST_ID_HEADER: "given"})
    assert response.headers[REQUEST_ID_HEADER] == "given"


async def test_health_ready_stays_red_until_the_provider_credential_is_current() -> None:
    settings = make_settings()
    runtime = replace(make_runtime(ScriptedProvider([]), settings), credentials_ready=_no_identity)
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://ops") as client:
        response = await client.get("/readyz")
    ready = ReadyResponse.model_validate(response.json())
    assert ready.status == "not_ready"
    assert ready.checks["provider_credentials"] is False


async def test_health_probe_live_answers_on_a_path_that_ends_without_z(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert LiveResponse.model_validate(response.json()).status == "live"


async def test_health_probe_ready_answers_200_when_ready(client: httpx.AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert ReadyResponse.model_validate(response.json()).status == "ready"


async def test_health_probe_ready_answers_503_with_its_checks_when_not_ready() -> None:
    settings = make_settings()
    runtime = replace(
        make_runtime(ScriptedProvider([""]), settings), credentials_ready=_no_identity
    )
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as bare:
        probe = await bare.get("/health/ready")
        local = await bare.get("/readyz")
    assert probe.status_code == 503
    assert ReadyResponse.model_validate(probe.json()).checks["provider_credentials"] is False
    assert local.status_code == 200
    assert local.json()["status"] == "not_ready"
