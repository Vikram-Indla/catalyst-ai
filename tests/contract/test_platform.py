"""The platform's contract: the envelope on every error, the rendered document."""

from dataclasses import replace

import httpx
import pytest
from fastapi import APIRouter, Request
from pydantic import BaseModel

from catalyst_ai.app import create_app, default_runtime, render_openapi
from catalyst_ai.config import Settings
from catalyst_ai.contract.errors import ErrorCode, ErrorEnvelope
from catalyst_ai.platform.auth import capability_of, envelope_of
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import MemoryStorage
from tools.origin import ORG, SUBJECT, SigningAuth

PROBE = "probe"
BODY = {"organization_id": str(ORG)}
probe = APIRouter()


class ProbeBody(BaseModel):
    organization_id: str


@probe.post("/probe", openapi_extra={"x-capability": PROBE})
async def probe_ok(body: ProbeBody, request: Request) -> dict[str, str]:
    envelope = envelope_of(request)
    return {"ok": body.organization_id[:4], "sub": envelope.subject if envelope else "none"}


@probe.post("/probe/catalog", openapi_extra={"x-capability": PROBE})
async def probe_catalog(body: ProbeBody) -> dict[str, str]:
    raise Error(ErrorCode.BUDGET_EXCEEDED, "over", retry_after_ms=3000)


@probe.post("/probe/crash", openapi_extra={"x-capability": PROBE})
async def probe_crash(body: ProbeBody) -> dict[str, str]:
    raise RuntimeError("boom")


@probe.post("/probe/validated/{number}", openapi_extra={"x-capability": PROBE})
async def probe_validated(number: int, body: ProbeBody) -> dict[str, int]:
    return {"number": number}


@pytest.fixture
async def probed(settings: Settings) -> httpx.AsyncClient:
    runtime = default_runtime(settings)
    app = create_app(settings, replace(runtime, storage=MemoryStorage(runtime.clock)))
    app.include_router(probe)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        auth=SigningAuth(capability_of(app)),
    )


async def test_a_signed_probe_is_served_and_sees_its_envelope(probed: httpx.AsyncClient) -> None:
    response = await probed.post("/probe", json=BODY)
    assert response.status_code == 200
    assert response.json() == {"ok": "1111", "sub": SUBJECT}
    assert envelope_of(Request({"type": "http", "headers": []})) is None


async def test_catalog_error_renders_the_envelope(probed: httpx.AsyncClient) -> None:
    response = await probed.post("/probe/catalog", json=BODY)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.BUDGET_EXCEEDED
    assert envelope.error.retry_after_ms == 3000


async def test_validation_failure_is_validation_invalid_input(probed: httpx.AsyncClient) -> None:
    response = await probed.post("/probe/validated/notanumber", json=BODY)
    assert response.status_code == 400
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.VALIDATION_INVALID_INPUT
    assert envelope.error.details[0].field == "path.number"


async def test_unhandled_error_is_internal_error_without_detail(probed: httpx.AsyncClient) -> None:
    response = await probed.post("/probe/crash", json=BODY)
    assert response.status_code == 500
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.INTERNAL_ERROR
    assert "boom" not in response.text


async def test_unknown_route_is_refused_like_everything_else(probed: httpx.AsyncClient) -> None:
    response = await probed.post("/nothing", json=BODY)
    assert response.status_code == 401
    assert ErrorEnvelope.model_validate(response.json()).error.code is ErrorCode.AUTH_ORIGIN_INVALID


def test_rendered_document_lists_every_health_operation(settings: Settings) -> None:
    document = render_openapi(create_app(settings))
    operations = {op["operationId"] for item in document["paths"].values() for op in item.values()}
    assert {"health.live", "health.ready", "improve_story.run"} <= operations
    for item in document["paths"].values():
        for operation in item.values():
            assert operation["x-capability"]
            assert "x-error-codes" in operation


def test_rendered_document_declares_the_proof_of_origin_and_an_open_catalog(
    settings: Settings,
) -> None:
    document = render_openapi(create_app(settings))
    scheme = document["components"]["securitySchemes"]["CatalystEnvelope"]
    assert scheme["scheme"] == "Catalyst-Envelope"
    assert document["security"] == [{"CatalystEnvelope": []}]
    assert document["paths"]["/healthz"]["get"]["security"] == []
    assert "security" not in document["paths"]["/v1/unfurl"]["post"]
    catalog = document["components"]["schemas"]["ErrorCode"]
    assert "enum" not in catalog
    assert "auth.origin.invalid" in catalog["x-extensible-enum"]
