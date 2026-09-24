"""The settings' refusals, asked in order: the first one found is the one the process dies with."""

from pydantic import SecretStr

from catalyst_ai.config import Environment, Settings
from catalyst_ai.config.deployed import NO_COLLECTOR, PORTS_SHARED, start_problem
from tools import origin


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "auth_public_keys": origin.PUBLIC_KEYS,
        "database_url": SecretStr("postgresql://u:p@h/d"),
    }
    values.update(overrides)
    return Settings.model_construct(None, **values)


def test_development_with_distinct_ports_starts() -> None:
    assert start_problem(_settings()) is None


def test_shared_ports_and_a_missing_collector_are_refused_first() -> None:
    assert start_problem(_settings(http_addr=":1", ops_addr=":1")) == PORTS_SHARED
    production = _settings(environment=Environment.PRODUCTION, otel_exporter_endpoint=None)
    assert start_problem(production) == NO_COLLECTOR


def test_a_deployed_process_without_a_location_is_refused_by_the_residency_rule() -> None:
    staging = _settings(environment=Environment.STAGING, provider_vertex_project="p")
    assert "PROVIDER_VERTEX_LOCATION" in (start_problem(staging) or "")
