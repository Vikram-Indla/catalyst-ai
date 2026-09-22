"""Alias resolution: the register row by default; a configured override must be a register id."""

import pytest
from pydantic import SecretStr

from catalyst_ai.config import Environment, Settings
from catalyst_ai.providers.gemini.aliases import UnknownModelError, resolve
from catalyst_ai.providers.gemini.models import FLASH, FLASH_LITE
from catalyst_ai.providers.port import ModelAlias
from tools import origin


def _settings(override: str | None = None) -> Settings:
    return Settings(
        environment=Environment.DEVELOPMENT,
        auth_public_keys=origin.PUBLIC_KEYS,
        database_url=SecretStr("postgresql://u:p@h/d"),
        model_text_default=override,
    )


def test_register_row_by_default() -> None:
    assert resolve(ModelAlias.TEXT_DEFAULT, _settings()) is FLASH
    assert resolve(ModelAlias.TEXT_FAST, _settings()) is FLASH_LITE


def test_override_with_a_register_id() -> None:
    assert (
        resolve(ModelAlias.TEXT_DEFAULT, _settings("gemini/" + FLASH_LITE.model_id)) is FLASH_LITE
    )


def test_override_outside_the_register_is_refused() -> None:
    with pytest.raises(UnknownModelError):
        resolve(ModelAlias.TEXT_DEFAULT, _settings("gemini/nope-1"))
