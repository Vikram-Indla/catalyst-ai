"""Settings: every validator refuses what it must; the environment is read once."""

import pytest
from pydantic import SecretStr, ValidationError

from catalyst_ai.config import Environment, Settings, load_settings
from catalyst_ai.config.settings import ENV_PREFIX, LogLevel

DB = "postgresql://u:p@h/d"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "service_tokens": [SecretStr("t")],
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


def test_tokens_split_from_a_comma_string() -> None:
    settings = _settings(service_tokens="a,b")
    assert [t.get_secret_value() for t in settings.service_tokens] == ["a", "b"]


@pytest.mark.parametrize("tokens", ["", "a,b,c", "a,,b"], ids=["none", "three", "empty"])
def test_tokens_bounded_and_non_empty(tokens: str) -> None:
    with pytest.raises(ValidationError):
        _settings(service_tokens=tokens)


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
        environment=Environment.PRODUCTION, otel_exporter_endpoint="http://otel"
    ).otel_exporter_endpoint


def test_extra_variables_refused() -> None:
    with pytest.raises(ValidationError):
        _settings(unknown=1)


def test_load_settings_reads_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(f"{ENV_PREFIX}ENVIRONMENT", "staging")
    monkeypatch.setenv(f"{ENV_PREFIX}SERVICE_TOKENS", "x")
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_URL", DB)
    assert load_settings().environment is Environment.STAGING
