"""What the eval harness and the recorder share: an inert runtime over the fixture directory."""

import importlib.util
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import httpx
from pydantic import SecretStr

from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.clock import SystemClock
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.gemini import GeminiProvider
from tools import rules

FIXTURES_ROOT = rules.FIXTURES / "providers" / "gemini"
INERT_DATABASE = "postgresql://eval:eval@localhost/eval"
UNLIMITED_MICROS = 10**12
CLIENT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class Case:
    """One line of a set."""

    id: str
    input: dict[str, object]
    tags: list[str]
    expected: dict[str, object]


def load_cases(set_file: Path) -> list[Case]:
    """Parse `set.jsonl`."""
    cases = []
    for line in set_file.read_text(encoding="utf-8").splitlines():
        if line.strip():
            raw = json.loads(line)
            cases.append(
                Case(
                    raw["id"],
                    raw["input"],
                    list(raw.get("tags", [])),
                    dict(raw.get("expected", {})),
                )
            )
    return cases


def load_graders(directory: Path) -> ModuleType:
    """Import `graders.py` of a set by path."""
    spec = importlib.util.spec_from_file_location(
        f"evals_{directory.name}_graders", directory / "graders.py"
    )
    if spec is None or spec.loader is None:
        message = f"no graders in {directory}"
        raise RuntimeError(message)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inert_settings(cache_ttl_seconds: int = 0) -> Settings:
    """Build settings that never reach a real provider; a zero cache TTL keeps every case a call."""
    return Settings(
        environment=Environment.DEVELOPMENT,
        service_tokens=[SecretStr("eval")],
        database_url=SecretStr(INERT_DATABASE),
        tenant_budget_default_micros_per_day=UNLIMITED_MICROS,
        capability_improve_story=CapabilitySettings(cache_ttl_seconds=cache_ttl_seconds),
    )


def runtime_over(
    transport: httpx.AsyncBaseTransport, settings: Settings | None = None
) -> RuntimeContext:
    """Build a runtime whose provider talks to the given transport and nothing else."""
    resolved = settings or inert_settings()
    clock = SystemClock()
    client = httpx.AsyncClient(timeout=CLIENT_TIMEOUT_S, transport=transport)
    return RuntimeContext(
        settings=resolved,
        provider=GeminiProvider(resolved, client, clock),
        cache=MemoryCache(clock),
        budgets=TenantBudgets(
            clock, resolved.tenant_budget_default_micros_per_day, resolved.tenant_concurrency_max
        ),
        clock=clock,
    )


def percentile(values: list[float], share: float) -> float:
    """Return the nearest-rank percentile; zero for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(share * len(ordered) + 0.5) - 1))
    return ordered[index]


Pipeline = Callable[..., Awaitable[ResponseEnvelope]]
Registry = dict[str, tuple[type[RequestEnvelope], Pipeline]]
