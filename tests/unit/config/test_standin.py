"""The stand-in switch: off by default, on in development, refused anywhere else."""

import pytest
from pydantic import SecretStr, ValidationError

from catalyst_ai.config import Environment, Settings
from tools import origin


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "auth_public_keys": origin.PUBLIC_KEYS,
        "database_url": SecretStr("postgresql://u:p@h/d"),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_the_stand_in_is_off_by_default_and_may_be_on_in_development() -> None:
    assert settings().provider_stand_in is False
    assert settings(provider_stand_in=True).provider_stand_in is True


def test_the_stand_in_is_refused_outside_development() -> None:
    with pytest.raises(ValidationError) as refused:
        settings(environment=Environment.STAGING, provider_stand_in=True)
    assert "PROVIDER_STAND_IN is development only" in str(refused.value)
