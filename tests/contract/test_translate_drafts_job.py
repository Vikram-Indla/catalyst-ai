"""The drafts job end to end: signed submit → 202, the worker drafts, the poll reads the drafts."""

import httpx

from catalyst_ai.app import create_app, job_runners
from catalyst_ai.contract.jobs import JobAccepted, JobStatus
from catalyst_ai.contract.translate_drafts import DraftsResponse
from catalyst_ai.platform.auth import KeyRegistry, capability_of
from catalyst_ai.platform.jobs import Worker
from catalyst_ai.platform.observability import SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import ORG, ScriptedProvider, make_runtime
from tests.unit.capabilities.translate.conftest import translation_text
from tools import origin
from tools.origin import SigningAuth

SUBMIT = "/v1/translate/drafts:jobs"
JOB_WINDOW_S = 3_600
BODY = {
    "organization_id": str(ORG),
    "capability_version": "1.2.0",
    "items": [
        {"record_ref": "theme-1", "field": "name", "en": "Digital Services"},
        {"record_ref": "theme-1", "field": "charter", "en": "  "},
    ],
    "glossary": [{"source": "Digital Services", "target": "الخدمات الرقمية"}],
    "glossary_version": "g1",
}


def _client(runtime: RuntimeContext, **claims: object) -> httpx.AsyncClient:
    app = create_app(runtime.settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
        auth=SigningAuth(capability_of(app), runtime.clock, claims=claims),
    )


async def test_translate_drafts_job_submits_runs_and_returns_machine_drafts() -> None:
    runtime = make_runtime(ScriptedProvider([translation_text("الخدمات الرقمية")]))
    job_exp = int(runtime.clock.now().timestamp()) + JOB_WINDOW_S
    client = _client(runtime, job_exp=job_exp)
    submitted = await client.post(SUBMIT, json=BODY)
    assert submitted.status_code == 202, submitted.text
    accepted = JobAccepted.model_validate(submitted.json())
    assert accepted.capability == "translate"
    keys = KeyRegistry.from_config(origin.PUBLIC_KEYS)
    worker = Worker(runtime, runtime.jobs, job_runners(), keys, SecurityCounters(runtime.metrics))
    assert await worker.run_once() is True
    poll = await client.get(f"/v1/jobs/{accepted.job_id}?organization_id={ORG}")
    status = JobStatus.model_validate(poll.json())
    assert status.state == "succeeded"
    result = DraftsResponse.model_validate(status.result)
    assert [d.status for d in result.drafts] == ["machine_draft"]
    assert result.drafts[0].glossary_hits == ["Digital Services"]
    assert [s.reason for s in result.skipped] == ["empty"]
    assert result.progress.total == 2


async def test_translate_drafts_job_needs_a_job_window_and_refuses_restricted_text() -> None:
    runtime = make_runtime(ScriptedProvider([translation_text("نص")]))
    no_window = await _client(runtime).post(SUBMIT, json=BODY)
    assert no_window.status_code == 401
    job_exp = int(runtime.clock.now().timestamp()) + JOB_WINDOW_S
    restricted = {**BODY, "items": [{"record_ref": "r", "field": "name", "en": "mail a@b.org"}]}
    refused = await _client(runtime, job_exp=job_exp).post(SUBMIT, json=restricted)
    assert refused.status_code == 422
    assert await runtime.jobs.count_jobs("queued") == 0
