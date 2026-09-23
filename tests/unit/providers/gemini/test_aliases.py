"""Alias resolution: the environment selects an alias, the register keeps the model."""

import pytest
from pydantic import SecretStr, ValidationError

from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.contract.models import ModelAlias, TextAlias
from catalyst_ai.providers.gemini.aliases import resolve, selected
from catalyst_ai.providers.gemini.models import EMBEDDING, FLASH
from tools import origin


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "auth_public_keys": origin.PUBLIC_KEYS,
        "database_url": SecretStr("postgresql://u:p@h/d"),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_the_environment_selects_the_alias_and_the_default_is_what_was_measured() -> None:
    settings = _settings()
    assert settings.model_text_alias is TextAlias.TEXT_DEFAULT
    assert resolve(ModelAlias.TEXT_DEFAULT, settings) == FLASH
    assert selected(settings) is TextAlias.TEXT_DEFAULT
    fast = _settings(model_text_alias=TextAlias.TEXT_FAST)
    assert resolve(ModelAlias.TEXT_DEFAULT, fast) == FLASH
    assert selected(fast) is TextAlias.TEXT_FAST


def test_a_capability_may_select_its_own_alias_over_the_environment() -> None:
    settings = _settings(
        model_text_alias=TextAlias.TEXT_DEFAULT,
        capability_translate=CapabilitySettings(model_alias=TextAlias.TEXT_FAST),
    )
    assert selected(settings, "translate") is TextAlias.TEXT_FAST
    assert selected(settings, "summarize") is TextAlias.TEXT_DEFAULT
    assert resolve(ModelAlias.TEXT_DEFAULT, settings, "translate") == FLASH


def test_the_index_and_the_grader_are_not_selectable() -> None:
    settings = _settings(model_text_alias=TextAlias.TEXT_FAST)
    assert resolve(ModelAlias.EMBED_DEFAULT, settings) == EMBEDDING
    assert resolve(ModelAlias.TEXT_FAST, settings) == FLASH


def test_an_unavailable_alias_fails_at_settings_load() -> None:
    """No stable long-context model is reachable: selecting one fails now, not at the first call."""
    with pytest.raises(ValidationError, match="unavailable"):
        _settings(model_text_alias=TextAlias.TEXT_LONG)
    with pytest.raises(ValidationError, match="unavailable"):
        _settings(capability_post_mortem=CapabilitySettings(model_alias=TextAlias.TEXT_LONG))


def test_an_alias_outside_the_vocabulary_fails_at_settings_load() -> None:
    """A model id is not an alias: the register owns ids, and configuration may not say one."""
    with pytest.raises(ValidationError):
        _settings(model_text_alias=FLASH.model_id)
    with pytest.raises(ValidationError):
        _settings(model_text_alias="embed-default")
    with pytest.raises(ValidationError):
        _settings(
            capability_summarize=CapabilitySettings.model_validate({"model_alias": "text-cheap"})
        )
