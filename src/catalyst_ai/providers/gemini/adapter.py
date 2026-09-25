"""GeminiProvider: the port over Gemini's REST API with deadline, retries, breaker and cost."""

from collections.abc import AsyncIterator
from typing import Any

import httpx

from catalyst_ai.config import Settings
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.resilience import Breaker, BreakerOpenError, RetryPolicy, retry_async
from catalyst_ai.providers.gemini import aliases, errors, streaming
from catalyst_ai.providers.gemini.credentials import TokenSource, authorization, token_source
from catalyst_ai.providers.gemini.embedding import EMBED_METHOD, build_embed_body, parse_embed
from catalyst_ai.providers.gemini.models import ModelSpec, billed_output_tokens
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    ModelAlias,
    StreamFrame,
)

API_VERSION = "v1"
CHARS_PER_TOKEN = 4
GENERATE_METHOD = "generateContent"
BREAKER_FAILURES = 5
BREAKER_OPEN_SECONDS = 30
MS_PER_SECOND = 1000
HTTP_ERROR_FLOOR = 400
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


def build_body(request: GenerateRequest, spec: ModelSpec) -> dict[str, Any]:
    """Build the REST body: system segments as the instruction, the rest as one user turn."""
    system = "\n\n".join(s.text for s in request.segments if s.role == "system")
    turn = "\n\n".join(s.text for s in request.segments if s.role != "system")
    config: dict[str, Any] = {
        "temperature": request.temperature,
        "maxOutputTokens": request.max_output_tokens,
    }
    if spec.thinking_level is not None:
        config["thinkingConfig"] = {"thinkingLevel": spec.thinking_level}
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
        aliases.check_pins(settings)
        self._settings = settings
        self._client = client
        self._clock = clock
        self._policy = policy or RetryPolicy()
        self._rng = self._policy.rng()
        self._breakers: dict[str, Breaker] = {}
        self._tokens: TokenSource = token_source(settings, client, clock)

    def _breaker(self, model_id: str) -> Breaker:
        return self._breakers.setdefault(
            model_id, Breaker(self._clock, BREAKER_FAILURES, BREAKER_OPEN_SECONDS)
        )

    def _url(self, spec: ModelSpec, method: str = GENERATE_METHOD) -> str:
        base = self._settings.provider_origin().rstrip("/")
        location = self._settings.provider_location()
        scope = f"projects/{self._settings.provider_vertex_project}/locations/{location}"
        return f"{base}/{API_VERSION}/{scope}/publishers/google/models/{spec.model_id}:{method}"

    async def _post(self, url: str, body: dict[str, Any], timeout_s: float) -> httpx.Response:
        headers = await authorization(self._tokens)
        response = await self._client.post(url, json=body, headers=headers, timeout=timeout_s)
        response.raise_for_status()
        return response

    async def _call_with_guards(
        self, spec: ModelSpec, url: str, body: dict[str, Any], timeout_ms: int, request_id: str
    ) -> httpx.Response:
        breaker = self._breaker(spec.model_id)
        breaker.before_call()
        try:
            response = await retry_async(
                lambda: self._post(url, body, timeout_ms / MS_PER_SECOND),
                self._policy,
                errors.is_retryable,
                self._rng,
            )
        except httpx.HTTPStatusError as error:
            breaker.record_failure()
            raise errors.from_status(
                error.response.status_code, len(error.response.content), request_id
            ) from error
        except httpx.HTTPError as error:
            breaker.record_failure()
            raise errors.from_transport(error, request_id) from error
        breaker.record_success()
        return response

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Run one generation; every failure is a catalog error with the raw detail in the log."""
        spec = aliases.resolve(request.alias, self._settings, request.capability)
        started = self._clock.now()
        try:
            response = await self._call_with_guards(
                spec,
                self._url(spec),
                build_body(request, spec),
                request.timeout_ms,
                request.request_id,
            )
        except BreakerOpenError as error:
            raise errors.from_transport(error, request.request_id) from error
        latency_ms = int((self._clock.now() - started).total_seconds() * MS_PER_SECOND)
        return _parse_generate(response.json(), spec, latency_ms, request.request_id)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Stream one generation: `delta` frames, one `usage`, one `done`; a failure raises.

        The breaker and the status mapping guard the connection; a stream is never retried,
        since a retry would repeat deltas the caller already passed on.
        """
        spec = aliases.resolve(request.alias, self._settings, request.capability)
        url = f"{self._url(spec, streaming.STREAM_METHOD)}?{streaming.STREAM_QUERY}"
        breaker = self._breaker(spec.model_id)
        started = self._clock.now()
        try:
            breaker.before_call()
            async with self._client.stream(
                "POST",
                url,
                json=build_body(request, spec),
                headers=await authorization(self._tokens),
                timeout=request.timeout_ms / MS_PER_SECOND,
            ) as response:
                if response.status_code >= HTTP_ERROR_FLOOR:
                    excerpt = len(await response.aread())
                    raise errors.from_status(response.status_code, excerpt, request.request_id)

                def latency_of() -> float:
                    return (self._clock.now() - started).total_seconds() * MS_PER_SECOND

                async for frame in streaming.frames_of(
                    response.aiter_lines(), spec, request.request_id, latency_of
                ):
                    yield frame
        except BreakerOpenError as error:
            raise errors.from_transport(error, request.request_id) from error
        except httpx.HTTPError as error:
            breaker.record_failure()
            raise errors.from_transport(error, request.request_id) from error
        breaker.record_success()

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        """Embed the texts in one batch call; tokens are estimated, the API reports none."""
        spec = aliases.resolve(request.alias, self._settings, request.capability)
        request_id = f"embed-{request.capability}"
        started = self._clock.now()
        try:
            response = await self._call_with_guards(
                spec,
                self._url(spec, EMBED_METHOD),
                build_embed_body(request),
                request.timeout_ms,
                request_id,
            )
        except BreakerOpenError as error:
            raise errors.from_transport(error, request_id) from error
        latency_ms = int((self._clock.now() - started).total_seconds() * MS_PER_SECOND)
        tokens = sum(self.count_tokens(request.alias, text) for text in request.texts)
        return parse_embed(response.json(), spec, tokens, latency_ms, request_id)

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        """Estimate tokens by characters; the provider's tokeniser earns a register row later."""
        del alias
        return max(1, len(text) // CHARS_PER_TOKEN)

    def model_id(self, alias: ModelAlias) -> str:
        """Return the register's concrete id for the alias under the current settings."""
        return aliases.resolve(alias, self._settings).model_id

    async def credentials_ready(self) -> bool:
        """Return whether the token is current; red until the workload's first one arrives."""
        return await self._tokens.ready()


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
    output_tokens = billed_output_tokens(usage_meta)
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
