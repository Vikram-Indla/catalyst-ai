"""The ops app: one registry with the process, no door in front of the scrape, no probe traffic."""

import httpx

from catalyst_ai.app import create_app, create_ops_app
from catalyst_ai.config import Settings
from catalyst_ai.platform.observability.metrics import JOB_QUARANTINED, REQUESTS
from catalyst_ai.platform.observability.security import SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)


def _pair() -> tuple[RuntimeContext, Settings]:
    settings = make_settings()
    return make_runtime(ScriptedProvider([]), settings), settings


async def test_the_scrape_needs_no_proof_of_origin_and_renders_the_shared_registry() -> None:
    runtime, settings = _pair()
    ops = create_ops_app(settings, runtime)
    transport = httpx.ASGITransport(app=ops, raise_app_exceptions=False)
    SecurityCounters(runtime.metrics).count(JOB_QUARANTINED, "bad_signature")
    async with httpx.AsyncClient(transport=transport, base_url="http://ops") as client:
        scrape = await client.get("/metrics")
        ready = await client.get("/readyz")
    assert scrape.status_code == 200, scrape.text
    assert 'catalyst_ai_job_quarantined_total{reason="bad_signature"} 1' in scrape.text
    assert ready.status_code == 200


async def test_probes_and_scrapes_are_not_counted_as_service_traffic() -> None:
    runtime, settings = _pair()
    ops = create_ops_app(settings, runtime)
    transport = httpx.ASGITransport(app=ops, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://ops") as client:
        await client.get("/healthz")
        await client.get("/readyz")
        await client.get("/metrics")
    assert runtime.metrics.total(REQUESTS) == 0


async def test_the_contract_app_refuses_the_scrape_path_like_any_other() -> None:
    runtime, settings = _pair()
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        response = await client.get("/metrics")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.origin.invalid"
