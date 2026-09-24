"""Settings: every validator refuses what it must; the environment is read once."""

import pytest
from pydantic import SecretStr, ValidationError

from catalyst_ai.config import Environment, Settings, load_settings, parse_public_keys
from catalyst_ai.config.residency import DEVELOPMENT_LOCATION, regional_endpoint
from catalyst_ai.config.settings import ENV_PREFIX, PUBLIC_KEY_BYTES, LogLevel
from tools import origin

DB = "postgresql://u:p@h/d"
PROJECT = "catalyst-ai-test"
LOGINS: dict[str, object] = {
    "database_url": SecretStr("postgresql://serve:p@h/d"),
    "database_worker_url": SecretStr("postgresql://worker:p@h/d"),
    "database_migrate_url": SecretStr("postgresql://owner:p@h/d"),
    "provider_vertex_location": DEVELOPMENT_LOCATION,
}


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "auth_public_keys": origin.PUBLIC_KEYS,
        "database_url": SecretStr(DB),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_defaults() -> None:
    settings = _settings()
    assert settings.http_addr == ":8090"
    assert settings.ops_addr == ":9091"
    assert settings.log_level is LogLevel.INFO
    assert settings.tenant_concurrency_max == 8


def test_public_keys_parse_to_bounded_entries() -> None:
    entries = parse_public_keys(origin.BOTH_PUBLIC_KEYS)
    assert [entry.key_id for entry in entries] == [origin.KEY_ID, origin.SECOND_KEY_ID]
    assert all(len(entry.raw) == PUBLIC_KEY_BYTES for entry in entries)
    assert _settings(auth_public_keys=origin.BOTH_PUBLIC_KEYS).auth_max_ttl_seconds == 60


@pytest.mark.parametrize(
    "keys",
    [
        "",
        origin.PUBLIC_KEYS + "," + origin.PUBLIC_KEYS,
        ",".join([origin.PUBLIC_KEYS, origin.SECOND_SIGNER.public_entry, "k3:" + "A" * 43]),
        "nocolon",
        "k1:not*base64",
        "k1:c2hvcnQ",
    ],
    ids=["none", "duplicate id", "three", "no colon", "not base64url", "not 32 bytes"],
)
def test_public_keys_refused_when_malformed(keys: str) -> None:
    with pytest.raises(ValidationError):
        _settings(auth_public_keys=keys)


@pytest.mark.parametrize(
    ("field", "value"),
    [("auth_clock_skew_seconds", 61), ("auth_max_ttl_seconds", 0), ("auth_max_ttl_seconds", 301)],
)
def test_origin_tolerances_are_bounded(field: str, value: int) -> None:
    with pytest.raises(ValidationError):
        _settings(**{field: value})


@pytest.mark.parametrize("url", ["mysql://u:p@h/d", "postgresql://h/d"], ids=["scheme", "no host"])
def test_database_url_validated(url: str) -> None:
    with pytest.raises(ValidationError):
        _settings(database_url=SecretStr(url))


@pytest.mark.parametrize(
    "addr", ["8090", "host:port", ""], ids=["no colon", "non-numeric", "empty"]
)
def test_addr_validated(addr: str) -> None:
    with pytest.raises(ValidationError):
        _settings(http_addr=addr)


def test_addr_with_host() -> None:
    assert _settings(http_addr="127.0.0.1:1").http_addr == "127.0.0.1:1"


def test_ports_must_differ() -> None:
    with pytest.raises(ValidationError):
        _settings(http_addr=":1", ops_addr=":1")


def test_production_requires_otel() -> None:
    with pytest.raises(ValidationError):
        _settings(environment=Environment.PRODUCTION)
    assert _settings(
        environment=Environment.PRODUCTION,
        otel_exporter_endpoint="http://otel",
        provider_vertex_project=PROJECT,
        **LOGINS,
    ).otel_exporter_endpoint


@pytest.mark.parametrize(
    "overrides",
    [
        {"provider_gemini_base_url": "https://generativelanguage.googleapis.com"},
        {"provider_gemini_base_url": "https://aiplatform.googleapis.com"},
        {"provider_vertex_project": ""},
        {"provider_access_token": SecretStr("developer-token")},
        {"provider_vertex_location": None},
        {"provider_vertex_location": "us-central1"},
    ],
    ids=[
        "developer api",
        "global endpoint",
        "no project",
        "developer token",
        "no location",
        "outside the kingdom",
    ],
)
@pytest.mark.parametrize("environment", [Environment.STAGING, Environment.PRODUCTION])
def test_a_deployed_process_sends_tenant_text_only_to_the_region(
    environment: Environment, overrides: dict[str, object]
) -> None:
    values: dict[str, object] = {
        "environment": environment,
        "otel_exporter_endpoint": "http://otel",
        "provider_vertex_project": PROJECT,
        **LOGINS,
    }
    assert _settings(**values).environment is environment
    values.update(overrides)
    with pytest.raises(ValidationError):
        _settings(**values)


def test_development_may_point_anywhere_with_a_developer_token() -> None:
    settings = _settings(
        provider_gemini_base_url="https://localhost:9000",
        provider_access_token=SecretStr("developer-token"),
    )
    assert settings.provider_vertex_project == ""
    assert _settings().provider_origin() == regional_endpoint(DEVELOPMENT_LOCATION)
    assert settings.provider_origin() == "https://localhost:9000"


def test_extra_variables_refused() -> None:
    with pytest.raises(ValidationError):
        _settings(unknown=1)


def test_load_settings_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}ENVIRONMENT", "staging")
    monkeypatch.setenv(f"{ENV_PREFIX}AUTH_PUBLIC_KEYS", origin.PUBLIC_KEYS)
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_URL", "postgresql://serve:p@h/d")
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_WORKER_URL", "postgresql://worker:p@h/d")
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_MIGRATE_URL", "postgresql://owner:p@h/d")
    monkeypatch.setenv(f"{ENV_PREFIX}PROVIDER_VERTEX_PROJECT", PROJECT)
    monkeypatch.setenv(f"{ENV_PREFIX}PROVIDER_VERTEX_LOCATION", DEVELOPMENT_LOCATION)
    assert load_settings().environment is Environment.STAGING


def test_a_deployed_process_needs_three_logins() -> None:
    deployed: dict[str, object] = {
        "environment": Environment.STAGING,
        "provider_vertex_project": PROJECT,
    }
    with pytest.raises(ValidationError):
        _settings(**deployed, database_worker_url=SecretStr(DB), database_migrate_url=SecretStr(DB))
    three = _settings(**deployed, **LOGINS)
    assert three.database_worker_url is not None
    with pytest.raises(ValidationError):
        _settings(database_worker_url=SecretStr("mysql://u:p@h/d"))
