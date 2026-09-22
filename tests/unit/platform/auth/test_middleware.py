"""The door's helpers: the capability of a route through included routers; the tenant of a body."""

from uuid import UUID

from fastapi import APIRouter, FastAPI

from catalyst_ai.platform.auth import capability_of, organization_of

ORG = "11111111-1111-7111-8111-111111111111"


def _scope(method: str, path: str) -> dict[str, object]:
    return {"type": "http", "method": method, "path": path, "root_path": ""}


def test_capability_of_walks_included_routers_and_their_prefixes() -> None:
    app = FastAPI()
    plain = APIRouter()
    prefixed = APIRouter()

    @plain.post("/v1/one", openapi_extra={"x-capability": "one"})
    async def one() -> dict[str, str]:
        return {}

    @prefixed.post("/two", openapi_extra={"x-capability": "two"})
    async def two() -> dict[str, str]:
        return {}

    @app.post("/v1/bare")
    async def bare() -> dict[str, str]:
        return {}

    app.include_router(plain)
    app.include_router(prefixed, prefix="/v1/p")
    lookup = capability_of(app)
    assert lookup(_scope("POST", "/v1/one")) == "one"
    assert lookup(_scope("POST", "/v1/p/two")) == "two"
    assert lookup(_scope("GET", "/v1/one")) is None
    assert lookup(_scope("POST", "/v1/bare")) is None
    assert lookup(_scope("POST", "/v1/nothing")) is None


def test_organization_of_reads_the_tenant_or_nothing() -> None:
    assert organization_of(b'{"organization_id": "' + ORG.encode() + b'"}') == UUID(ORG)
    assert organization_of(b'{"organization_id": "nope"}') is None
    assert organization_of(b'{"organization_id": 7}') is None
    assert organization_of(b"[1, 2]") is None
    assert organization_of(b"not json") is None
    assert organization_of(b"") is None
