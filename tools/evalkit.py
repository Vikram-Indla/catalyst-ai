"""What the eval harness and the recorder share: the registry, an inert runtime, the database."""

import contextlib
import importlib.util
import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import httpx
from pydantic import SecretStr
from testcontainers.core.utils import inside_container
from testcontainers.postgres import PostgresContainer

from catalyst_ai.capabilities.assistant.pipeline import stream as assistant_stream
from catalyst_ai.capabilities.documents import ask as documents_ask
from catalyst_ai.capabilities.documents import generate as documents_generate
from catalyst_ai.capabilities.documents import run_ingest
from catalyst_ai.capabilities.generate_children import run as generate_children
from catalyst_ai.capabilities.generate_tests import run as generate_tests
from catalyst_ai.capabilities.improve_story import run as improve_story
from catalyst_ai.capabilities.post_mortem import run as post_mortem
from catalyst_ai.capabilities.propose_workflow import run as propose_workflow
from catalyst_ai.capabilities.release_notes import run as release_notes
from catalyst_ai.capabilities.search import run as search_run
from catalyst_ai.capabilities.search import run_upsert
from catalyst_ai.capabilities.summarize import run as summarize
from catalyst_ai.capabilities.translate import run as translate
from catalyst_ai.capabilities.unfurl.pipeline import run as unfurl_run
from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.contract.assistant import TurnRequest, TurnResponse
from catalyst_ai.contract.documents import AskRequest, DraftRequest, IngestRequest
from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope
from catalyst_ai.contract.generate_children import GenerateChildrenRequest
from catalyst_ai.contract.generate_tests import GenerateTestsRequest
from catalyst_ai.contract.improve_story import ImproveStoryRequest
from catalyst_ai.contract.post_mortem import PostMortemRequest
from catalyst_ai.contract.propose_workflow import ProposeWorkflowRequest
from catalyst_ai.contract.release_notes import ReleaseNotesRequest
from catalyst_ai.contract.search import IndexUpsertRequest, SearchRequest
from catalyst_ai.contract.summarize import SummarizeRequest
from catalyst_ai.contract.translate import TranslateRequest
from catalyst_ai.contract.unfurl import UnfurlRequest
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.clock import SystemClock
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryStorage, PostgresStorage, Storage, migrate
from catalyst_ai.providers.gemini import GeminiProvider
from tools import origin, rules

FIXTURES_ROOT = rules.FIXTURES / "providers" / "gemini"
INERT_DATABASE = "postgresql://eval:eval@localhost/eval"
UNLIMITED_MICROS = 10**12
CLIENT_TIMEOUT_S = 30.0
DATABASE_VARIABLE = "CATALYST_AI_EVAL_DATABASE_URL"
DATABASE_IMAGE = rules.CI_DATABASE_IMAGE
MIGRATIONS = Path("db/migrations")
CORPUS_FILE = "corpus.jsonl"
UNTERMINATED = "the stream ended without done"
UPSERT_BATCH = 100
COMMAND_TIMEOUT_S = 30.0


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
        auth_public_keys=origin.PUBLIC_KEYS,
        database_url=SecretStr(INERT_DATABASE),
        tenant_budget_default_micros_per_day=UNLIMITED_MICROS,
        capability_improve_story=CapabilitySettings(cache_ttl_seconds=cache_ttl_seconds),
    )


def runtime_over(
    transport: httpx.AsyncBaseTransport,
    settings: Settings | None = None,
    storage: Storage | None = None,
) -> RuntimeContext:
    """Build a runtime over the given transport; storage is in memory unless one is given."""
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
        storage=storage or MemoryStorage(clock),
    )


def percentile(values: list[float], share: float) -> float:
    """Return the nearest-rank percentile; zero for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round(share * len(ordered) + 0.5) - 1))
    return ordered[index]


Pipeline = Callable[..., Awaitable[ResponseEnvelope]]
Setup = Callable[[RuntimeContext, Path], Awaitable[None]]


@dataclass(frozen=True)
class SetSpec:
    """How a set runs: its request model, its pipeline, an optional setup, the database need."""

    request: type[RequestEnvelope]
    pipeline: Pipeline
    setup: Setup | None = None
    needs_database: bool = False


async def index_corpus(runtime: RuntimeContext, directory: Path) -> None:
    """Index `corpus.jsonl` through the upsert operation, per organisation, in batches."""
    lines = [
        json.loads(line)
        for line in (directory / CORPUS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    by_organization: dict[str, list[dict[str, object]]] = {}
    for line in lines:
        by_organization.setdefault(str(line["organization_id"]), []).append(line)
    keys = ("external_id", "kind", "title", "text", "data_class", "content_hash")
    for organization_id, documents in by_organization.items():
        for start in range(0, len(documents), UPSERT_BATCH):
            batch = documents[start : start + UPSERT_BATCH]
            request = IndexUpsertRequest.model_validate(
                {
                    "organization_id": organization_id,
                    "capability_version": "1.0.0",
                    "corpus": "work_items",
                    "documents": [{k: d[k] for k in keys} for d in batch],
                }
            )
            await run_upsert(request, runtime, f"setup-{organization_id[:8]}-{start}")


async def assistant_turn(
    request: TurnRequest, runtime: RuntimeContext, request_id: str
) -> TurnResponse:
    """Run a turn through the streaming path and return the response its `done` carries."""
    result: TurnResponse | None = None
    async for event in assistant_stream(request, runtime, request_id):
        if event.kind == "done":
            result = event.result
    if result is None:
        raise RuntimeError(UNTERMINATED)
    return result


async def ingest_corpus(runtime: RuntimeContext, directory: Path) -> None:
    """Index `corpus.jsonl` through the ingest operation, one document per line."""
    lines = [
        json.loads(line)
        for line in (directory / CORPUS_FILE).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for index, line in enumerate(lines):
        await run_ingest(IngestRequest.model_validate(line), runtime, f"setup-{index}")


REGISTRY: dict[str, SetSpec] = {
    "improve-story": SetSpec(ImproveStoryRequest, improve_story),
    "generate-children": SetSpec(GenerateChildrenRequest, generate_children),
    "search": SetSpec(SearchRequest, search_run, setup=index_corpus, needs_database=True),
    "summarize": SetSpec(SummarizeRequest, summarize),
    "translate": SetSpec(TranslateRequest, translate),
    "propose-workflow": SetSpec(ProposeWorkflowRequest, propose_workflow),
    "release-notes": SetSpec(ReleaseNotesRequest, release_notes),
    "generate-tests": SetSpec(GenerateTestsRequest, generate_tests),
    "post-mortem": SetSpec(PostMortemRequest, post_mortem),
    "documents": SetSpec(AskRequest, documents_ask, setup=ingest_corpus),
    "documents-generate": SetSpec(DraftRequest, documents_generate),
    "documents-ingest": SetSpec(IngestRequest, run_ingest),
    "assistant": SetSpec(TurnRequest, assistant_turn, setup=ingest_corpus),
    "unfurl": SetSpec(UnfurlRequest, unfurl_run),
}


def container_dsn(container: PostgresContainer) -> str:
    """Return the connection string that reaches the container from here.

    Inside a container the published port is not routable, so the bridge address and the
    container's own port are used; outside, the mapped port on the host.
    """
    if inside_container():
        bridge = container.get_docker_client().bridge_ip(container.get_wrapped_container().id)
        credentials = f"{container.username}:{container.password}"
        return f"postgresql://{credentials}@{bridge}:{container.port}/{container.dbname}"
    return str(container.get_connection_url())


@contextlib.asynccontextmanager
async def database(spec: SetSpec) -> AsyncIterator[Storage]:
    """Yield the storage a set runs over: memory, the named database, or a throwaway container."""
    clock = SystemClock()
    if not spec.needs_database:
        yield MemoryStorage(clock)
        return
    url = os.environ.get(DATABASE_VARIABLE)
    if url:
        async with _postgres(url, clock) as storage:
            yield storage
        return
    with PostgresContainer(DATABASE_IMAGE, driver=None) as container:
        async with _postgres(container_dsn(container), clock) as storage:
            yield storage


@contextlib.asynccontextmanager
async def _postgres(url: str, clock: SystemClock) -> AsyncIterator[PostgresStorage]:
    await migrate(url, MIGRATIONS)
    storage = PostgresStorage(url, clock, 4, COMMAND_TIMEOUT_S)
    await storage.connect()
    try:
        yield storage
    finally:
        await storage.close()
