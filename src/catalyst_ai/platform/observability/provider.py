"""The port, metered: every provider call counted by capability, model and outcome.

The composition root wraps the real adapter in this, so no capability can forget to report and
no capability has to remember: the numbers come from the one seam every call crosses. Tokens,
cost and latency are the row's own fields (`ARCH-010 §1`); the text never enters a metric.
"""

from collections.abc import AsyncIterator
from datetime import datetime

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability.metrics import (
    PROVIDER_CALLS,
    PROVIDER_COST_MICROS,
    PROVIDER_SECONDS,
    PROVIDER_TOKENS,
    Metrics,
)
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    ModelAlias,
    Provider,
    StreamFrame,
)

OK = "ok"
INPUT = "input"
OUTPUT = "output"


class MeteredProvider:
    """A `Provider` that records what every call cost before handing the result back."""

    def __init__(self, provider: Provider, metrics: Metrics, clock: Clock) -> None:
        """Wrap the real provider; the clock is the one the process measures with."""
        self._provider = provider
        self._metrics = metrics
        self._clock = clock

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Time the call, record it under its outcome, and return what the adapter returned."""
        started = self._clock.now()
        try:
            result = await self._provider.generate(request)
        except Error as error:
            self._record(request, self._provider.model_id(request.alias), error.code.value, started)
            raise
        self._record(request, result.model_id, OK, started, result.usage)
        return result

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Pass the frames through, then record the stream as one call with its usage."""
        started = self._clock.now()
        usage: Usage | None = None
        model_id = self._provider.model_id(request.alias)
        try:
            async for frame in self._provider.stream(request):
                usage = frame.usage or usage
                yield frame
        except Error as error:
            self._record(request, model_id, error.code.value, started, usage)
            raise
        self._record(request, model_id, OK, started, usage)

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        """Time the embedding call and record it like a generation."""
        started = self._clock.now()
        labels = {"capability": request.capability, "model": self._provider.model_id(request.alias)}
        try:
            result = await self._provider.embed(request)
        except Error as error:
            self._metrics.count(PROVIDER_CALLS, {**labels, "outcome": error.code.value})
            raise
        self._metrics.count(PROVIDER_CALLS, {**labels, "outcome": OK})
        self._seconds(started, labels)
        self._usage(request.organization_id.hex, labels, result.usage)
        return result

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        """Delegate: counting tokens reaches no provider."""
        return self._provider.count_tokens(alias, text)

    def model_id(self, alias: ModelAlias) -> str:
        """Delegate: the concrete model behind an alias."""
        return self._provider.model_id(alias)

    def _record(
        self,
        request: GenerateRequest,
        model_id: str,
        outcome: str,
        started: datetime,
        usage: Usage | None = None,
    ) -> None:
        labels = {"capability": request.capability, "model": model_id}
        self._metrics.count(PROVIDER_CALLS, {**labels, "outcome": outcome})
        self._seconds(started, labels)
        self._usage(request.organization_id.hex, labels, usage)

    def _seconds(self, started: datetime, labels: dict[str, str]) -> None:
        seconds = (self._clock.now() - started).total_seconds()
        self._metrics.observe(PROVIDER_SECONDS, seconds, labels)

    def _usage(self, organization: str, labels: dict[str, str], usage: Usage | None) -> None:
        if usage is None:
            return
        self._metrics.count(PROVIDER_TOKENS, {**labels, "direction": INPUT}, usage.input_tokens)
        self._metrics.count(PROVIDER_TOKENS, {**labels, "direction": OUTPUT}, usage.output_tokens)
        self._metrics.count(
            PROVIDER_COST_MICROS, {**labels, "organization": organization}, usage.cost_micros
        )
