"""The composition root: settings, middleware, routers, the storage lifecycle, the contract."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import APIRouter, FastAPI, Request
from fastapi.openapi.utils import get_openapi

from catalyst_ai.capabilities.generate_children import router as generate_children_router
from catalyst_ai.capabilities.generate_tests import router as generate_tests_router
from catalyst_ai.capabilities.improve_story import router as improve_story_router
from catalyst_ai.capabilities.post_mortem import router as post_mortem_router
from catalyst_ai.capabilities.propose_workflow import router as propose_workflow_router
from catalyst_ai.capabilities.release_notes import router as release_notes_router
from catalyst_ai.capabilities.search import router as search_router
from catalyst_ai.capabilities.summarize import router as summarize_router
from catalyst_ai.capabilities.translate import router as translate_router
from catalyst_ai.config import Settings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.health import LiveResponse, ReadyResponse
from catalyst_ai.platform.auth import ServiceTokenMiddleware
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.clock import SystemClock
from catalyst_ai.platform.httpserver import (
    RequestIdMiddleware,
    install_error_handlers,
    with_error_responses,
)
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import PostgresStorage, StorageUnavailableError
from catalyst_ai.providers.gemini import GeminiProvider

CONTRACT_VERSION = "0.1.0"
TITLE = "Catalyst One AI service"
PLATFORM_CAPABILITY = "platform"
PLATFORM_ERROR_CODES = (
    ErrorCode.AUTH_INVALID.value,
    ErrorCode.VALIDATION_INVALID_INPUT.value,
    ErrorCode.INTERNAL_ERROR.value,
)

STORAGE_COMMAND_TIMEOUT_S = 15.0
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
    checks = {"settings": True, "storage": await runtime.storage.ready()}
    return ReadyResponse(status="ready" if all(checks.values()) else "not_ready", checks=checks)


def _with_examples(document: dict[str, Any]) -> dict[str, Any]:
    for path_item in document.get("paths", {}).values():
        for operation in path_item.values():
            responses = operation.get("responses", {})
            operation.setdefault("x-error-codes", list(PLATFORM_ERROR_CODES))
            for status, response in responses.items():
                if status == "200":
                    response.setdefault("x-example", "see the contract tests")
    return document


def render_openapi(app: FastAPI) -> dict[str, Any]:
    """Render the contract document from the app; `make api` writes it, the drift check compares."""
    document = get_openapi(
        title=TITLE,
        version=CONTRACT_VERSION,
        openapi_version="3.1.0",
        routes=app.routes,
        description="One contract for the Go backend; see ENGINEERING.md.",
    )
    return with_error_responses(_with_examples(document))


PROVIDER_CLIENT_TIMEOUT_S = 30.0


def default_runtime(
    settings: Settings, transport: httpx.AsyncBaseTransport | None = None
) -> RuntimeContext:
    """Build the production runtime: system clock, Gemini adapter, in-process cache and caps."""
    clock = SystemClock()
    client = httpx.AsyncClient(timeout=PROVIDER_CLIENT_TIMEOUT_S, transport=transport)
    return RuntimeContext(
        settings=settings,
        provider=GeminiProvider(settings, client, clock),
        cache=MemoryCache(clock),
        budgets=TenantBudgets(
            clock, settings.tenant_budget_default_micros_per_day, settings.tenant_concurrency_max
        ),
        clock=clock,
        storage=PostgresStorage(
            settings.database_url.get_secret_value(),
            clock,
            settings.database_pool_max,
            STORAGE_COMMAND_TIMEOUT_S,
        ),
    )


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


def create_app(settings: Settings, runtime: RuntimeContext | None = None) -> FastAPI:
    """Assemble the app: request ids, the service token, the handlers, the routers, the runtime."""
    app = FastAPI(
        title=TITLE, version=CONTRACT_VERSION, docs_url=None, redoc_url=None, lifespan=_lifespan
    )
    app.state.runtime = runtime or default_runtime(settings)
    app.add_middleware(ServiceTokenMiddleware, tokens=settings.service_tokens)
    app.add_middleware(RequestIdMiddleware)
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
    return app
