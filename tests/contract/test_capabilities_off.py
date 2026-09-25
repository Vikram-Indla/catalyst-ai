"""The environment's switch: with the capabilities off, every capability operation refuses by design.

A staging whose region does not yet serve the models runs with the capabilities off. Every
operation the contract document declares for a capability is called with a request it would
otherwise accept, signed as the backend signs it, and answers `503 ai.capability.disabled`; the
probes and the jobs' polling keep answering.
"""

import hashlib
import json
from pathlib import Path

import httpx

from catalyst_ai.app import create_app, render_openapi
from catalyst_ai.contract.errors import ErrorCode, ErrorEnvelope
from catalyst_ai.platform.auth import capability_of
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import evalkit, origin, rules
from tools.origin import SigningAuth

PLATFORM = "platform"
JOB_WINDOW_S = 3_600
DISABLED = 503
STREAM = "text/event-stream"


def _indexing_bodies() -> dict[str, dict[str, object]]:
    title, text = "Login with SSO", "Members sign in with the company identity provider."
    digest = hashlib.sha256((title + "\n" + text).encode()).hexdigest()
    base = {
        "organization_id": str(origin.ORG),
        "capability_version": "1.0.0",
        "corpus": "work_items",
    }
    document = {
        "external_id": "A-1",
        "kind": "story",
        "title": title,
        "text": text,
        "data_class": "INTERNAL",
        "content_hash": digest,
    }
    return {
        "IndexUpsertRequest": {**base, "documents": [document]},
        "IndexDeleteRequest": {**base, "external_ids": ["A-1"]},
    }


def _bodies() -> dict[str, dict[str, object]]:
    """Return a request each operation would accept, by its request model's name."""
    found = _indexing_bodies()
    for name, spec in evalkit.REGISTRY.items():
        first = (Path(rules.EVALS) / name / "set.jsonl").read_text(encoding="utf-8").splitlines()[0]
        found.setdefault(spec.request.__name__, json.loads(first)["input"])
    return found


def _operations(document: dict[str, object]) -> list[tuple[str, str]]:
    """Return (path, request model) for every capability operation that takes a body."""
    paths = document["paths"]
    assert isinstance(paths, dict)
    found = []
    for path, item in paths.items():
        for operation in item.values():
            body = (operation.get("requestBody") or {}).get("content", {}).get("application/json")
            if operation.get("x-capability") == PLATFORM or body is None:
                continue
            found.append((path, body["schema"]["$ref"].rsplit("/", 1)[-1]))
    return found


async def test_every_capability_refuses_by_design_with_the_capabilities_off() -> None:
    settings = make_settings(capabilities_enabled=False)
    runtime = make_runtime(ScriptedProvider([""]), settings)
    app = create_app(settings, runtime)
    job_exp = int(runtime.clock.now().timestamp()) + JOB_WINDOW_S
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
        auth=SigningAuth(capability_of(app), runtime.clock, claims={"job_exp": job_exp}),
    )
    bodies = _bodies()
    operations = _operations(render_openapi(app))
    assert len(operations) >= 20
    for path, model in operations:
        assert model in bodies, f"no request for {path} ({model})"
        response = await client.post(path, json=bodies[model])
        if response.headers.get("content-type", "").startswith(STREAM):
            assert "event: error" in response.text, path
            assert ErrorCode.CAPABILITY_DISABLED.value in response.text, path
            continue
        assert response.status_code == DISABLED, (path, response.text)
        refused = ErrorEnvelope.model_validate(response.json())
        assert refused.error.code is ErrorCode.CAPABILITY_DISABLED, path
    assert (await client.get("/health/live")).status_code == 200
    assert (await client.get("/health/ready")).status_code == 200
    assert provider_calls(runtime) == 0


def provider_calls(runtime: object) -> int:
    """Return how many calls reached the provider double."""
    provider = getattr(runtime, "provider", None)
    return len(getattr(provider, "calls", [])) + len(getattr(provider, "embed_calls", []))


async def test_a_capability_answers_again_with_the_switch_on() -> None:
    settings = make_settings()
    runtime = make_runtime(ScriptedProvider([""]), settings)
    app = create_app(settings, runtime)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
        auth=SigningAuth(capability_of(app), runtime.clock),
    )
    response = await client.post("/v1/index/delete", json=_indexing_bodies()["IndexDeleteRequest"])
    assert response.status_code != DISABLED
