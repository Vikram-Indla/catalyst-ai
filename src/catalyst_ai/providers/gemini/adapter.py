"""GeminiProvider: the port over Gemini's REST API with deadline, retries, breaker and cost."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from catalyst_ai.config import Settings
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.resilience import Breaker, BreakerOpenError, RetryPolicy, retry_async
from catalyst_ai.providers.gemini import aliases, errors
from catalyst_ai.providers.gemini.models import ModelSpec
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    ModelAlias,
    StreamFrame,
)

API_VERSION = "v1beta"
KEY_HEADER = "x-goog-api-key"
CHARS_PER_TOKEN = 4
BREAKER_FAILURES = 5
BREAKER_OPEN_SECONDS = 30
MS_PER_SECOND = 1000
SCHEMA_KEYS = ("type", "properties", "required", "items", "enum", "description", "nullable")


def _schema_for_provider(schema: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, value in schema.items():
        if key not in SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {
                n: _schema_for_provider(s) for n, s in value.items() if isinstance(s, dict)
            }
        elif key == "items" and isinstance(value, dict):
            cleaned[key] = _schema_for_provider(value)
        else:
            cleaned[key] = value
    return cleaned


def build_body(request: GenerateRequest) -> dict[str, Any]:
    """Build the REST body: system segments as the instruction, the rest as one user turn."""
    system = "\n\n".join(s.text for s in request.segments if s.role == "system")
    turn = "\n\n".join(s.text for s in request.segments if s.role != "system")
    config: dict[str, Any] = {
        "temperature": request.temperature,
        "maxOutputTokens": request.max_output_tokens,
    }
    if request.output_schema is not None:
        config["responseMimeType"] = "application/json"
        config["responseSchema"] = _schema_for_provider(request.output_schema)
    body: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": turn}]}],
        "generationConfig": config,
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    return body


class GeminiProvider:
    """The adapter; one instance per process, one breaker per model."""

    def __init__(
        self,
        settings: Settings,
        client: httpx.AsyncClient,
        clock: Clock,
        policy: RetryPolicy | None = None,
    ) -> None:
        """Bind the settings, the client (its transport is the recording seam) and the clock."""
        self._settings = settings
        self._client = client
        self._clock = clock
        self._policy = policy or RetryPolicy()
        self._rng = self._policy.rng()
        self._breakers: dict[str, Breaker] = {}

    def _breaker(self, model_id: str) -> Breaker:
        return self._breakers.setdefault(
            model_id, Breaker(self._clock, BREAKER_FAILURES, BREAKER_OPEN_SECONDS)
        )

    def _url(self, spec: ModelSpec) -> str:
        base = self._settings.provider_gemini_base_url.rstrip("/")
        return f"{base}/{API_VERSION}/models/{spec.model_id}:generateContent"

    def _headers(self) -> dict[str, str]:
        key = self._settings.provider_gemini_api_key
        return {KEY_HEADER: key.get_secret_value() if key else ""}

    async def _post(self, url: str, body: dict[str, Any], timeout_s: float) -> httpx.Response:
        response = await self._client.post(
            url, json=body, headers=self._headers(), timeout=timeout_s
        )
        response.raise_for_status()
        return response

    async def _call_with_guards(self, spec: ModelSpec, request: GenerateRequest) -> httpx.Response:
        breaker = self._breaker(spec.model_id)
        breaker.before_call()
        try:
            response = await retry_async(
                lambda: self._post(
                    self._url(spec), build_body(request), request.timeout_ms / MS_PER_SECOND
                ),
                self._policy,
                errors.is_retryable,
                self._rng,
            )
        except httpx.HTTPStatusError as error:
            breaker.record_failure()
            raise errors.from_status(
                error.response.status_code, len(error.response.content), request.request_id
            ) from error
        except httpx.HTTPError as error:
            breaker.record_failure()
            raise errors.from_transport(error, request.request_id) from error
        breaker.record_success()
        return response

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Run one generation; every failure is a catalog error with the raw detail in the log."""
        spec = aliases.resolve(request.alias, self._settings)
        started = self._clock.now()
        try:
            response = await self._call_with_guards(spec, request)
        except BreakerOpenError as error:
            raise errors.from_transport(error, request.request_id) from error
        latency_ms = int((self._clock.now() - started).total_seconds() * MS_PER_SECOND)
        return _parse_generate(response.json(), spec, latency_ms, request.request_id)

    def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Streaming arrives with the assistant capability; until then the port refuses it."""
        del request
        message = "streaming is not implemented by this adapter yet"
        raise NotImplementedError(message)

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        """Embeddings arrive with the retrieval package; until then the port refuses it."""
        del request
        message = "embeddings are not implemented by this adapter yet"
        raise NotImplementedError(message)

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        """Estimate tokens by characters; the provider's tokeniser earns a register row later."""
        del alias
        return max(1, len(text) // CHARS_PER_TOKEN)


def _parse_generate(
    payload: dict[str, Any], spec: ModelSpec, latency_ms: int, request_id: str
) -> GenerateResult:
    candidates = payload.get("candidates") or []
    blocked = errors.from_finish_reason(
        (candidates[0].get("finishReason") if candidates else None)
        or (payload.get("promptFeedback") or {}).get("blockReason"),
        request_id,
    )
    if blocked is not None:
        raise blocked
    parts = (candidates[0].get("content") or {}).get("parts") or [] if candidates else []
    text = "".join(str(part.get("text", "")) for part in parts)
    usage_meta = payload.get("usageMetadata") or {}
    input_tokens = int(usage_meta.get("promptTokenCount", 0))
    output_tokens = int(usage_meta.get("candidatesTokenCount", 0))
    usage = Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_micros=spec.cost_micros(input_tokens, output_tokens),
        latency_ms=latency_ms,
        cache_hit=False,
    )
    return GenerateResult(
        text=text, model_id=str(payload.get("modelVersion") or spec.model_id), usage=usage
    )
