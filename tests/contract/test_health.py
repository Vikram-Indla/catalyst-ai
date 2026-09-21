"""health.live and health.ready through the app: shape, exemption from auth, request id."""

import httpx

from catalyst_ai.contract.health import LiveResponse, ReadyResponse
from catalyst_ai.platform.httpserver import REQUEST_ID_HEADER


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
    assert ready.checks == {"settings": True, "storage": True}


async def test_health_live_echoes_a_supplied_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/healthz", headers={REQUEST_ID_HEADER: "given"})
    assert response.headers[REQUEST_ID_HEADER] == "given"
