"""Proof of origin at the door: refused without detail, logged with the reason, counted; exempt health."""

import json
import logging
from dataclasses import replace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI

from catalyst_ai.app import create_app
from catalyst_ai.contract.errors import ErrorCode, ErrorEnvelope
from catalyst_ai.platform.auth import capability_of
from catalyst_ai.platform.observability import ORIGIN_REFUSED
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    FrozenClock,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import origin
from tools.origin import SigningAuth, unsigned

PATH = "/v1/improve-story"
OTHER = UUID("22222222-2222-7222-8222-222222222222")


def _body(organization_id: UUID = origin.ORG) -> dict[str, object]:
    return {
        "organization_id": str(organization_id),
        "capability_version": "1.0.0",
        "mode": "clarify",
        "item_type": "Story",
        "title": "Login with SSO",
        "description": "As a member I want to log in with the company SSO so I need no password.",
    }


RAW = json.dumps(_body()).encode()


def _app() -> tuple[httpx.AsyncClient, FastAPI, FrozenClock]:
    settings = make_settings()
    runtime = make_runtime(ScriptedProvider([GOOD_TEXT] * 4), settings)
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        auth=SigningAuth(capability_of(app), runtime.clock),
    )
    clock = runtime.clock
    assert isinstance(clock, FrozenClock)
    return client, app, clock


def _refused(response: httpx.Response) -> ErrorEnvelope:
    assert response.status_code == 401
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.AUTH_ORIGIN_INVALID
    assert envelope.error.details == []
    assert envelope.error.message == "proof of origin required"
    return envelope


async def test_a_signed_call_is_served_and_the_health_routes_need_no_proof() -> None:
    client, app, _ = _app()
    assert (await client.post(PATH, json=_body())).status_code == 200
    assert (await client.get("/healthz", auth=unsigned)).status_code == 200
    assert app.state.security.value(ORIGIN_REFUSED) == 0


async def test_organisation_mismatch_is_refused_without_detail_and_logged_with_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, app, clock = _app()
    forged = SigningAuth(capability_of(app), clock, org=str(OTHER))
    with caplog.at_level(logging.WARNING, logger="catalyst_ai.security"):
        response = await client.post(PATH, json=_body(), auth=forged)
    _refused(response)
    assert "organization" not in response.text
    record = next(r for r in caplog.records if r.getMessage() == ORIGIN_REFUSED)
    assert vars(record)["reason"] == "organization_mismatch"
    assert vars(record)["capability"] == "improve-story"
    assert app.state.security.value(ORIGIN_REFUSED, "organization_mismatch") == 1


async def test_a_replayed_envelope_is_refused_the_second_time() -> None:
    client, app, clock = _app()
    header = origin.Signer(clock=clock).sign(origin.ORG, "improve-story", RAW)
    headers = {"Authorization": header, "Content-Type": "application/json"}
    first = await client.post(PATH, content=RAW, headers=headers, auth=unsigned)
    assert first.status_code == 200
    _refused(await client.post(PATH, content=RAW, headers=headers, auth=unsigned))
    assert app.state.security.value(ORIGIN_REFUSED, "replayed") == 1


async def test_expired_unknown_key_and_edited_payload_are_refused() -> None:
    client, app, clock = _app()
    now = int(clock.now().timestamp())
    expired = SigningAuth(capability_of(app), clock, iat=now - 120, exp=now - 60)
    _refused(await client.post(PATH, json=_body(), auth=expired))
    unknown = SigningAuth(capability_of(app), clock, kid="retired-key")
    _refused(await client.post(PATH, json=_body(), auth=unknown))
    header = origin.Signer(clock=clock).sign(origin.ORG, "improve-story", RAW)
    edited = RAW.replace(b"log in", b"log out")
    headers = {"Authorization": header, "Content-Type": "application/json"}
    _refused(await client.post(PATH, content=edited, headers=headers, auth=unsigned))
    counters = app.state.security
    assert counters.value(ORIGIN_REFUSED, "expired") == 1
    assert counters.value(ORIGIN_REFUSED, "unknown_key") == 1
    assert counters.value(ORIGIN_REFUSED, "body_mismatch") == 1


async def test_the_old_bearer_and_a_missing_header_are_refused_alike() -> None:
    client, app, _ = _app()
    bearer = {"Authorization": "Bearer test-token"}
    _refused(await client.post(PATH, json=_body(), headers=bearer, auth=unsigned))
    _refused(await client.post(PATH, json=_body(), auth=unsigned))
    assert app.state.security.value(ORIGIN_REFUSED, "malformed") == 1
    assert app.state.security.value(ORIGIN_REFUSED, "missing") == 1


class _DownStorage(MemoryStorage):
    async def remember_nonce(self, nonce: str, expires_at: int, now: int) -> bool:
        raise StorageUnavailableError("ConnectionRefusedError")


async def test_a_replay_store_outage_is_a_retryable_refusal_not_a_verdict() -> None:
    settings = make_settings()
    runtime = make_runtime(ScriptedProvider([GOOD_TEXT]), settings)
    runtime = replace(runtime, storage=_DownStorage(runtime.clock))
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        auth=SigningAuth(capability_of(app), runtime.clock),
    )
    response = await client.post(PATH, json=_body())
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    envelope = ErrorEnvelope.model_validate(response.json())
    assert envelope.error.code is ErrorCode.AUTH_ORIGIN_UNVERIFIABLE
    assert app.state.security.value(ORIGIN_REFUSED, "unverifiable") == 1
