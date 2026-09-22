"""The jobs router declares its operation the way every capability does."""

from fastapi.routing import APIRoute

from catalyst_ai.platform.jobs import jobs_router
from catalyst_ai.platform.jobs.routes import CAPABILITY, ERROR_CODES


def test_the_get_operation_is_declared_with_its_capability_and_codes() -> None:
    routes = [r for r in jobs_router.routes if isinstance(r, APIRoute)]
    assert [r.path for r in routes] == ["/v1/jobs/{job_id}"]
    route = routes[0]
    assert route.methods == {"GET"}
    assert route.operation_id == "jobs.get"
    assert route.openapi_extra is not None
    assert route.openapi_extra["x-capability"] == CAPABILITY
    assert CAPABILITY == "jobs"
    assert route.openapi_extra["x-error-codes"] == [code.value for code in ERROR_CODES]
