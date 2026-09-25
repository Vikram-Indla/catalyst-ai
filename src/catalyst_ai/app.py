"""The composition root: settings, middleware, routers, the storage lifecycle, the contract."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from catalyst_ai.capabilities.assistant import router as assistant_router
from catalyst_ai.capabilities.brief import router as brief_router
from catalyst_ai.capabilities.documents import descriptor as documents_descriptor
from catalyst_ai.capabilities.documents import router as documents_router
from catalyst_ai.capabilities.documents.jobs import run_ingest_payload
from catalyst_ai.capabilities.generate_children import router as generate_children_router
from catalyst_ai.capabilities.generate_tests import router as generate_tests_router
from catalyst_ai.capabilities.improve_story import router as improve_story_router
from catalyst_ai.capabilities.interpret_query import router as interpret_query_router
from catalyst_ai.capabilities.post_mortem import router as post_mortem_router
from catalyst_ai.capabilities.propose_workflow import router as propose_workflow_router
from catalyst_ai.capabilities.release_notes import router as release_notes_router
from catalyst_ai.capabilities.search import router as search_router
from catalyst_ai.capabilities.summarize import router as summarize_router
from catalyst_ai.capabilities.translate import descriptor as translate_descriptor
from catalyst_ai.capabilities.translate import router as translate_router
from catalyst_ai.capabilities.translate.jobs import run_drafts_payload
from catalyst_ai.capabilities.unfurl import router as unfurl_router
from catalyst_ai.config import Settings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.health import LiveResponse, ReadyResponse
from catalyst_ai.contract.translate_drafts import DraftsResponse
from catalyst_ai.platform.auth import (
    EXEMPT_PATHS,
    Bounds,
    KeyRegistry,
    OriginMiddleware,
    Verifier,
    capability_of,
)
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.clock import SystemClock
from catalyst_ai.platform.httpserver import (
    RequestIdMiddleware,
    install_error_handlers,
    with_error_responses,
    with_job_results,
)
from catalyst_ai.platform.jobs import JobRunner, jobs_router
from catalyst_ai.platform.observability import (
    MeteredProvider,
    RequestMetricsMiddleware,
    SecurityCounters,
    metrics_router,
)
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import PostgresJobStore, PostgresStorage, StorageUnavailableError
from catalyst_ai.providers.gemini import GeminiProvider

CONTRACT_VERSION = "0.1.0"
TITLE = "Catalyst One AI service"
PLATFORM_CAPABILITY = "platform"
PLATFORM_ERROR_CODES = (
    ErrorCode.AUTH_ORIGIN_INVALID.value,
    ErrorCode.AUTH_ORIGIN_UNVERIFIABLE.value,
    ErrorCode.VALIDATION_INVALID_INPUT.value,
    ErrorCode.INTERNAL_ERROR.value,
)

STORAGE_COMMAND_TIMEOUT_S = 15.0
SECURITY_SCHEME = "CatalystEnvelope"
EXTENSIBLE_ENUM = "x-extensible-enum"
SECURITY = MappingProxyType(
    {
        "type": "http",
        "scheme": "Catalyst-Envelope",
        "description": (
            "Proof of origin, signed by the backend: `<claims>.<signature>` where claims is the "
            "base64url of a JSON object {iss: backend, aud: catalyst-ai, org, cap, sub, iat, exp "
            "(at most 60 s after iat), jti, kid, bh (hex SHA-256 of the request body), job_exp?} "
            "and signature is the base64url of the Ed25519 signature over the ASCII bytes of the "
            "claims segment, by the private key `kid` names. The service holds public keys only."
        ),
    }
)
log = logging.getLogger(__name__)
health = APIRouter(tags=["health"])


@health.get(
    "/healthz",
    operation_id="health.live",
    response_model=LiveResponse,
    openapi_extra={
        "x-capability": PLATFORM_CAPABILITY,
        "x-capability-version": CONTRACT_VERSION,
        "x-error-codes": [],
    },
)
async def live() -> LiveResponse:
    """Report that the process is up."""
    return LiveResponse(status="live")


@health.get(
    "/readyz",
    operation_id="health.ready",
    response_model=ReadyResponse,
    openapi_extra={
        "x-capability": PLATFORM_CAPABILITY,
        "x-capability-version": CONTRACT_VERSION,
        "x-error-codes": [],
    },
)
async def ready(request: Request) -> ReadyResponse:
    """Report whether the process can serve; every dependency it has answers."""
    runtime: RuntimeContext = request.app.state.runtime
    checks = {
        "settings": True,
        "storage": await runtime.storage.ready(),
        "provider_credentials": await runtime.credentials_ready(),
    }
    checks.update(_worker_check(request))
    return ReadyResponse(status="ready" if all(checks.values()) else "not_ready", checks=checks)


PROBE_EXTRA = MappingProxyType(
    {
        "x-capability": PLATFORM_CAPABILITY,
        "x-capability-version": CONTRACT_VERSION,
        "x-error-codes": [],
    }
)
NOT_READY = 503


@health.get(
    "/health/live",
    operation_id="health.probe_live",
    response_model=LiveResponse,
    openapi_extra=dict(PROBE_EXTRA),
)
async def probe_live() -> LiveResponse:
    """Report that the process is up, on the path a platform's probe uses (none ends in `z`)."""
    return await live()


@health.get(
    "/health/ready",
    operation_id="health.probe_ready",
    response_model=ReadyResponse,
    responses={NOT_READY: {"model": ReadyResponse, "description": "not ready; the checks say why"}},
    openapi_extra=dict(PROBE_EXTRA),
)
async def probe_ready(request: Request) -> JSONResponse:
    """Report readiness as a probe reads it: 200 when ready, 503 with the same checks when not."""
    verdict = await ready(request)
    code = 200 if verdict.status == "ready" else NOT_READY
    return JSONResponse(status_code=code, content=verdict.model_dump(mode="json"))


def _worker_check(request: Request) -> dict[str, bool]:
    """Report whether this process still takes work: the worker's drain, or the API's."""
    worker = getattr(request.app.state, "worker", None)
    if worker is not None:
        return {"worker": not worker.draining}
    return {"serving": not getattr(request.app.state, "draining", False)}


def _with_examples(document: dict[str, Any]) -> dict[str, Any]:
    for path_item in document.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses", {})
            operation.setdefault("x-error-codes", list(PLATFORM_ERROR_CODES))
            for status, response in responses.items():
                if status.startswith("2"):
                    response.setdefault("x-example", "see the contract tests")
    return document


JOB_RESULTS = MappingProxyType({"translate.drafts_job": DraftsResponse})


def render_openapi(app: FastAPI) -> dict[str, Any]:
    """Render the contract document from the app; `make api` writes it, the drift check compares."""
    document = get_openapi(
        title=TITLE,
        version=CONTRACT_VERSION,
        openapi_version="3.1.0",
        routes=app.routes,
        description="One contract for the Go backend; see ENGINEERING.md.",
    )
    published = with_job_results(document, JOB_RESULTS)
    return _with_open_catalog(with_error_responses(_with_security(_with_examples(published))))


def _with_open_catalog(document: dict[str, Any]) -> dict[str, Any]:
    """Declare the error catalog as an enum that grows: a new code is additive, never breaking."""
    schema = document["components"]["schemas"][ErrorCode.__name__]
    schema[EXTENSIBLE_ENUM] = schema.pop("enum")
    return document


def _with_security(document: dict[str, Any]) -> dict[str, Any]:
    """Declare the proof of origin every operation needs; the health routes declare none."""
    document.setdefault("components", {})["securitySchemes"] = {SECURITY_SCHEME: dict(SECURITY)}
    document["security"] = [{SECURITY_SCHEME: []}]
    for path, item in document["paths"].items():
        for operation in item.values():
            if path in EXEMPT_PATHS:
                operation["security"] = []
    return document


PROVIDER_CLIENT_TIMEOUT_S = 30.0


def default_runtime(
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None = None,
    dsn: str | None = None,
) -> RuntimeContext:
    """Build the production runtime: system clock, Gemini adapter, in-process cache and caps.

    The database login is serve's unless the caller names another (the worker names its own).
    """
    clock = SystemClock()
    client = httpx.AsyncClient(timeout=PROVIDER_CLIENT_TIMEOUT_S, transport=transport)
    storage = PostgresStorage(
        dsn or settings.database_url.get_secret_value(),
        clock,
        settings.database_pool_max,
        STORAGE_COMMAND_TIMEOUT_S,
    )
    provider = GeminiProvider(settings, client, clock)
    return RuntimeContext(
        settings=settings,
        provider=provider,
        cache=MemoryCache(clock),
        budgets=TenantBudgets(
            clock, settings.tenant_budget_default_micros_per_day, settings.tenant_concurrency_max
        ),
        clock=clock,
        storage=storage,
        jobs=PostgresJobStore(storage),
        credentials_ready=provider.credentials_ready,
    )


def job_runners() -> dict[str, JobRunner]:
    """Return the capabilities a job may run, by name; assembled here so the worker imports none."""
    return {
        documents_descriptor.name: run_ingest_payload,
        translate_descriptor.name: run_drafts_payload,
    }


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    storage = app.state.runtime.storage
    if isinstance(storage, PostgresStorage):
        try:
            await storage.connect()
        except StorageUnavailableError as error:
            log.warning("storage unavailable at startup", extra={"kind": str(error)})
    yield
    if isinstance(storage, PostgresStorage):
        await storage.close()


def create_ops_app(settings: Settings, runtime: RuntimeContext) -> FastAPI:
    """Build the ops port's app: liveness, readiness and the scrape, and nothing else.

    It shares the process's runtime and its registry, and it carries neither the proof of
    origin (a collector signs nothing) nor the request metrics (a probe is not traffic).
    """
    app = FastAPI(title=TITLE, version=CONTRACT_VERSION, docs_url=None, redoc_url=None)
    app.state.runtime = runtime
    app.state.metrics = runtime.metrics
    app.state.settings = settings
    app.state.draining = False
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health)
    app.include_router(metrics_router)
    return app


def create_app(settings: Settings, runtime: RuntimeContext | None = None) -> FastAPI:
    """Assemble the app: request ids, proof of origin, the handlers, the routers, the runtime."""
    app = FastAPI(
        title=TITLE, version=CONTRACT_VERSION, docs_url=None, redoc_url=None, lifespan=_lifespan
    )
    context = runtime or default_runtime(settings)
    metrics = context.metrics
    app.state.metrics = metrics
    app.state.draining = False
    app.state.security = SecurityCounters(metrics)
    context = replace(context, provider=MeteredProvider(context.provider, metrics, context.clock))
    app.state.runtime = context
    verifier = Verifier(
        KeyRegistry.from_config(settings.auth_public_keys),
        context.storage,
        Bounds(settings.auth_clock_skew_seconds, settings.auth_max_ttl_seconds),
    )
    app.add_middleware(
        OriginMiddleware,
        verifier=verifier,
        counters=app.state.security,
        clock=context.clock,
        lookup=capability_of(app),
    )
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(RequestMetricsMiddleware, metrics=app.state.metrics, clock=context.clock)
    install_error_handlers(app)
    app.include_router(health)
    app.include_router(improve_story_router)
    app.include_router(generate_children_router)
    app.include_router(search_router)
    app.include_router(summarize_router)
    app.include_router(translate_router)
    app.include_router(propose_workflow_router)
    app.include_router(release_notes_router)
    app.include_router(generate_tests_router)
    app.include_router(post_mortem_router)
    app.include_router(documents_router)
    app.include_router(assistant_router)
    app.include_router(unfurl_router)
    app.include_router(interpret_query_router)
    app.include_router(brief_router)
    app.include_router(jobs_router)
    return app
