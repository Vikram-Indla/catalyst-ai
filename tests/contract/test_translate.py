"""translate.run through the app: the fixture path, the target rule, every listed error."""

from collections.abc import AsyncIterator

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.app import create_app
from catalyst_ai.config import CapabilitySettings, Settings
from catalyst_ai.contract.translate import TranslateResponse
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.recorded import RecordedTransport
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.translate.conftest import FIELD, FIELD_AR, translation_text
from tools import evalkit

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "providers" / "gemini" / "translate"
ORG = "11111111-1111-7111-8111-111111111111"
PATH = "/v1/translate"


def _body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "field",
        "text": FIELD,
        "target_language": "ar",
    }
    body.update(overrides)
    return body


def _client(runtime: RuntimeContext, settings: Settings) -> httpx.AsyncClient:
    app = create_app(settings, runtime)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=5.0,
        headers={"Authorization": "Bearer test-token"},
    )


def _scripted(texts: list[str], **overrides: object) -> tuple[httpx.AsyncClient, ScriptedProvider]:
    provider = ScriptedProvider(texts)
    settings = make_settings(service_tokens=[SecretStr("test-token")], **overrides)
    return _client(make_runtime(provider, settings), settings), provider


@pytest.fixture
async def recorded() -> AsyncIterator[httpx.AsyncClient]:
    settings = evalkit.inert_settings(cache_ttl_seconds=3600).model_copy(
        update={"service_tokens": [SecretStr("test-token")]}
    )
    runtime = evalkit.runtime_over(RecordedTransport(FIXTURES), settings)
    client = _client(runtime, settings)
    yield client
    await client.aclose()


async def test_translate_run_returns_a_translation_from_the_recorded_fixture(
    recorded: httpx.AsyncClient,
) -> None:
    body = evalkit.load_cases(REPO_ROOT / "evals" / "translate" / "set.jsonl")[0].input
    response = await recorded.post(PATH, json=body)
    assert response.status_code == 200, response.text
    translated = TranslateResponse.model_validate(response.json())
    assert translated.translated_text
    assert translated.target_language == body["target_language"]
    assert translated.structure_preserved is True


async def test_translate_run_without_a_target_is_rejected_with_the_detail() -> None:
    client, provider = _scripted([translation_text()])
    response = await client.post(PATH, json=_body(target_language=None))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ai.input.rejected"
    assert response.json()["error"]["details"][0]["code"] == "target_language_required"
    assert provider.calls == []


async def test_translate_run_keeps_structure_and_flags_a_broken_one() -> None:
    client, _ = _scripted([translation_text()])
    response = await client.post(PATH, json=_body())
    assert response.status_code == 200, response.text
    assert response.json()["structure_preserved"] is True
    assert response.json()["detected_language"] == "en"
    flat, _ = _scripted([translation_text(FIELD_AR.replace("- ", ""))])
    broken = await flat.post(PATH, json=_body())
    assert broken.json()["structure_preserved"] is False
    assert broken.json()["confidence"] < 1.0


async def test_translate_run_switch_version_scanner_budget_and_outputs() -> None:
    off, provider = _scripted(
        [translation_text()], capability_translate=CapabilitySettings(enabled=False)
    )
    disabled = await off.post(PATH, json=_body())
    assert disabled.status_code == 503
    assert disabled.json()["error"]["code"] == "ai.capability.disabled"
    assert provider.calls == []
    client, _ = _scripted([translation_text()])
    version = await client.post(PATH, json=_body(capability_version="2.0.0"))
    assert version.json()["error"]["code"] == "ai.contract.version_mismatch"
    scanned = await client.post(PATH, json=_body(text="mail someone@example.com"))
    assert scanned.json()["error"]["code"] == "ai.input.rejected"
    capped, _ = _scripted([translation_text()], tenant_budget_default_micros_per_day=1)
    budget = await capped.post(PATH, json=_body())
    assert budget.json()["error"]["code"] == "ai.budget.exceeded"
    invalid, _ = _scripted(["not json"])
    broken = await invalid.post(PATH, json=_body())
    assert broken.json()["error"]["code"] == "ai.output.invalid"
    leaking, _ = _scripted([translation_text(FIELD_AR + " https://evil.example/x")])
    unsafe = await leaking.post(PATH, json=_body())
    assert unsafe.json()["error"]["code"] == "ai.output.unsafe"


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (Fault(status=503), "ai.provider.unavailable"),
        (Fault(raises=httpx.ReadTimeout), "ai.provider.timeout"),
        (Fault(status=429), "ai.provider.quota"),
        (Fault(status=400), "ai.provider.rejected"),
    ],
    ids=["unavailable", "timeout", "quota", "rejected"],
)
async def test_translate_run_provider_failures(fault: Fault, code: str) -> None:
    settings = evalkit.inert_settings().model_copy(
        update={"service_tokens": [SecretStr("test-token")]}
    )
    base = evalkit.runtime_over(FaultTransport([fault]), settings)
    client_http = httpx.AsyncClient(transport=FaultTransport([fault]), timeout=1.0)
    provider = GeminiProvider(
        settings, client_http, base.clock, RetryPolicy(attempts=1, base_ms=0, max_ms=0, seed=1)
    )
    runtime = RuntimeContext(
        settings=settings,
        provider=provider,
        cache=base.cache,
        budgets=base.budgets,
        clock=base.clock,
        storage=base.storage,
    )
    client = _client(runtime, settings)
    response = await client.post(PATH, json=_body())
    assert response.json()["error"]["code"] == code
