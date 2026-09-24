"""The settings' cross-field refusals, in one place: what makes a process refuse to start.

Each rule lives with its reason in its own module (`residency`, `logins`); this module only asks
them in order and returns the first refusal, so the settings validator stays one call.
"""

from typing import TYPE_CHECKING

from catalyst_ai.config.logins import logins_problem
from catalyst_ai.config.residency import residency_problem

if TYPE_CHECKING:
    from catalyst_ai.config.settings import Settings

PORTS_SHARED = "HTTP_ADDR and OPS_ADDR must differ"
NO_COLLECTOR = "OTEL_EXPORTER_ENDPOINT is required in production"
PRODUCTION = "production"


def _secret(value: object) -> str | None:
    reveal = getattr(value, "get_secret_value", None)
    return str(reveal()) if reveal is not None else None


def start_problem(settings: "Settings") -> str | None:
    """Return why a process with these settings must not start, or None."""
    deployed = settings.environment.value != "development"
    problems = (
        PORTS_SHARED if settings.http_addr == settings.ops_addr else None,
        NO_COLLECTOR
        if settings.environment.value == PRODUCTION and settings.otel_exporter_endpoint is None
        else None,
        residency_problem(
            deployed,
            settings.provider_vertex_location,
            settings.provider_gemini_base_url,
            settings.provider_vertex_project,
            settings.provider_access_token is not None,
        ),
        logins_problem(
            deployed,
            settings.database_url.get_secret_value(),
            _secret(settings.database_worker_url),
            _secret(settings.database_migrate_url),
        ),
    )
    return next((problem for problem in problems if problem), None)
