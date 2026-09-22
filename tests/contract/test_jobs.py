"""The job contract: submit → 202 + Location, poll with Retry-After, a result for its organisation only."""

import base64
from dataclasses import replace
from datetime import timedelta
from uuid import UUID, uuid4

import httpx

from catalyst_ai.app import create_app, job_runners
from catalyst_ai.config import Settings
from catalyst_ai.contract.documents import IngestResponse
from catalyst_ai.contract.jobs import JobAccepted, JobStatus
from catalyst_ai.platform.auth import KeyRegistry, capability_of
from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.jobs import Worker
from catalyst_ai.platform.observability import JOB_QUARANTINED, SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryJobStore
from tests.unit.capabilities.documents.conftest import ingest_request, sha
from tests.unit.capabilities.improve_story.conftest import (
    FrozenClock,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import origin
from tools.origin import SigningAuth

SUBMIT = "/v1/documents/ingest:jobs"
INGEST = "/v1/documents/ingest"
OTHER = UUID("22222222-2222-7222-8222-222222222222")
JOB_WINDOW_S = 3_600


def _client(
    runtime: RuntimeContext, settings: Settings, **claims: object
) -> tuple[httpx.AsyncClient, SecurityCounters]:
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    client = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        auth=SigningAuth(capability_of(app), runtime.clock, claims=claims),
    )
    return client, app.state.security


def _runtime(**overrides: object) -> RuntimeContext:
    settings = make_settings(**overrides)
    runtime = make_runtime(ScriptedProvider([]), settings)
    return runtime


def _worker(runtime: RuntimeContext) -> tuple[Worker, SecurityCounters]:
    keys = KeyRegistry.from_config(origin.PUBLIC_KEYS)
    counters = SecurityCounters()
    return Worker(runtime, runtime.jobs, job_runners(), keys, counters), counters


def _job_exp(runtime: RuntimeContext) -> int:
    return int(runtime.clock.now().timestamp()) + JOB_WINDOW_S


async def test_documents_ingest_job_submit_poll_and_read_the_result() -> None:
    runtime = _runtime()
    client, _ = _client(runtime, runtime.settings, job_exp=_job_exp(runtime))
    body = ingest_request().model_dump(mode="json")
    submitted = await client.post(SUBMIT, json=body)
    assert submitted.status_code == 202, submitted.text
    accepted = JobAccepted.model_validate(submitted.json())
    assert accepted.state == "queued"
    assert submitted.headers["Location"] == f"/v1/jobs/{accepted.job_id}"
    assert submitted.headers["Retry-After"] == "2"
    poll = f"/v1/jobs/{accepted.job_id}?organization_id={body['organization_id']}"
    queued = await client.get(poll)
    assert queued.status_code == 200, queued.text
    assert JobStatus.model_validate(queued.json()).state == "queued"
    assert queued.headers["Retry-After"] == "2"
    worker, _ = _worker(runtime)
    assert await worker.run_once() is True
    done = await client.get(poll)
    status = JobStatus.model_validate(done.json())
    assert status.state == "succeeded"
    assert "Retry-After" not in done.headers
    assert status.result is not None
    result = IngestResponse.model_validate(status.result)
    assert result.state == "indexed"
    assert result.chunks == 2
    assert await worker.run_once() is False


async def test_documents_ingest_job_is_idempotent_by_body_and_organisation() -> None:
    runtime = _runtime()
    client, _ = _client(runtime, runtime.settings, job_exp=_job_exp(runtime))
    body = ingest_request().model_dump(mode="json")
    first = JobAccepted.model_validate((await client.post(SUBMIT, json=body)).json())
    second = JobAccepted.model_validate((await client.post(SUBMIT, json=body)).json())
    assert first.job_id == second.job_id
    other = ingest_request(document_id="doc-other").model_dump(mode="json")
    third = JobAccepted.model_validate((await client.post(SUBMIT, json=other)).json())
    assert third.job_id != first.job_id
    assert await runtime.jobs.count_jobs("queued") == 2


async def test_jobs_get_answers_its_organisation_only_and_404_otherwise() -> None:
    runtime = _runtime()
    client, _ = _client(runtime, runtime.settings, job_exp=_job_exp(runtime))
    body = ingest_request().model_dump(mode="json")
    accepted = JobAccepted.model_validate((await client.post(SUBMIT, json=body)).json())
    foreign = await client.get(f"/v1/jobs/{accepted.job_id}?organization_id={OTHER}")
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "ai.job.not_found"
    unknown = await client.get(f"/v1/jobs/{uuid4()}?organization_id={body['organization_id']}")
    assert unknown.status_code == 404
    unsigned_org = await client.get(f"/v1/jobs/{accepted.job_id}")
    assert unsigned_org.status_code == 401


async def test_documents_ingest_job_needs_a_job_window_in_the_envelope() -> None:
    runtime = _runtime()
    client, counters = _client(runtime, runtime.settings)
    response = await client.post(SUBMIT, json=ingest_request().model_dump(mode="json"))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.origin.invalid"
    assert counters.value("origin_refused", "no_job_window") == 1
    assert await runtime.jobs.count_jobs("queued") == 0


async def test_documents_ingest_above_the_line_is_a_job_not_a_call() -> None:
    runtime = _runtime()
    client, _ = _client(runtime, runtime.settings, job_exp=_job_exp(runtime))
    big = "# Big\n\n" + ("A line of text that repeats. " * 12_000)
    encoded = base64.b64encode(big.encode()).decode()
    request = ingest_request(text=None, content_base64=encoded, content_hash=sha(big))
    body = request.model_dump(mode="json")
    refused = await client.post(INGEST, json=body)
    assert refused.status_code == 413
    assert refused.json()["error"]["details"][0]["code"] == "use_the_job_operation"
    accepted = await client.post(SUBMIT, json=body)
    assert accepted.status_code == 202, accepted.text


async def test_jobs_get_shows_expired_for_a_job_past_its_window_that_never_ran() -> None:
    runtime = _runtime()
    now = int(runtime.clock.now().timestamp())
    client, _ = _client(runtime, runtime.settings, job_exp=now + 1)
    accepted = JobAccepted.model_validate(
        (await client.post(SUBMIT, json=ingest_request().model_dump(mode="json"))).json()
    )
    clock = runtime.clock
    assert isinstance(clock, FrozenClock)
    clock.at += timedelta(seconds=5)
    worker, _ = _worker(runtime)
    assert await worker.run_once() is True
    row = await runtime.jobs.read_job(origin.ORG, accepted.job_id)
    assert row is not None
    assert row.state == "expired"
    assert row.result is None


async def test_the_attackers_rows_are_quarantined_on_the_running_loop() -> None:
    """Six rows inserted straight into the store, as a database writer would, never run."""
    runtime = _runtime()
    store = runtime.jobs
    assert isinstance(store, MemoryJobStore)
    client, _ = _client(runtime, runtime.settings, job_exp=_job_exp(runtime))
    body = ingest_request().model_dump(mode="json")
    accepted = JobAccepted.model_validate((await client.post(SUBMIT, json=body)).json())
    legitimate = await store.read_job(origin.ORG, accepted.job_id)
    assert legitimate is not None
    forged = origin.Signer(origin.SECOND_SEED, origin.KEY_ID, runtime.clock)
    rows = {
        "no_envelope": replace(legitimate, id=new_id(), request_hash="h1", envelope=""),
        "made_up": replace(
            legitimate, id=new_id(), request_hash="h2", envelope="Catalyst-Envelope x.y"
        ),
        "other_org": replace(legitimate, id=new_id(), request_hash="h3", organization_id=OTHER),
        "other_cap": replace(legitimate, id=new_id(), request_hash="h4", capability="summarize"),
        "edited_payload": replace(
            legitimate, id=new_id(), request_hash="h5", payload=legitimate.payload + b" "
        ),
        "forged_key": replace(
            legitimate,
            id=new_id(),
            request_hash="h6",
            envelope=forged.sign(
                origin.ORG, "documents", legitimate.payload, job_exp=_job_exp(runtime)
            ),
        ),
    }
    for row in rows.values():
        store.plant(row)
    worker, counters = _worker(runtime)
    settled = 0
    while await worker.run_once():
        settled += 1
    assert settled == 7
    for name, row in rows.items():
        stored = await store.read_job(row.organization_id, row.id)
        assert stored is not None, name
        assert stored.state == "quarantined", name
        assert stored.result is None, name
    assert counters.value(JOB_QUARANTINED) == 6
    real = await store.read_job(origin.ORG, accepted.job_id)
    assert real is not None
    assert real.state == "succeeded"
