"""An unknown variable with the service's prefix refuses the start, named, its value never shown."""

import os
from pathlib import Path

import pytest

from catalyst_ai.config import Settings, UnknownSettingsError, load_settings
from catalyst_ai.config.settings import ENV_PREFIX, NESTING
from catalyst_ai.config.unknown import TOOLING, declared, refuse_unknown, unknown
from tools import origin

ROOT = Path(__file__).resolve().parents[3]
KNOWN = declared(Settings, ENV_PREFIX, NESTING)


def base_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [n for n in os.environ if n.upper().startswith(ENV_PREFIX)]:
        monkeypatch.delenv(name)
    monkeypatch.setenv(f"{ENV_PREFIX}ENVIRONMENT", "development")
    monkeypatch.setenv(f"{ENV_PREFIX}AUTH_PUBLIC_KEYS", origin.PUBLIC_KEYS)
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_URL", "postgresql://serve:p@h/d")


def test_a_misspelt_capabilities_switch_refuses_the_start_by_name_not_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}CAPABILITIES_ENABLD", "false-and-secretish")
    monkeypatch.setenv(f"{ENV_PREFIX}DISABLED_CAPABILITES", "summarize")
    with pytest.raises(UnknownSettingsError) as refused:
        load_settings(os.environ)
    message = str(refused.value)
    assert "CATALYST_AI_CAPABILITIES_ENABLD" in message
    assert "CATALYST_AI_DISABLED_CAPABILITES" in message
    assert "false-and-secretish" not in message
    assert "summarize" not in message


def test_the_declared_settings_and_the_tooling_start(monkeypatch: pytest.MonkeyPatch) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}CAPABILITIES_ENABLED", "false")
    monkeypatch.setenv(f"{ENV_PREFIX}CAPABILITY_SUMMARIZE__ENABLED", "false")
    for name in TOOLING:
        monkeypatch.setenv(name, "x")
    settings = load_settings(os.environ)
    assert settings.capabilities_enabled is False
    assert settings.capability_summarize.enabled is False


def test_the_single_underscore_spelling_is_refused_not_ignored() -> None:
    with pytest.raises(UnknownSettingsError, match="CAPABILITY_SUMMARIZE_ENABLED"):
        refuse_unknown(
            {"CATALYST_AI_CAPABILITY_SUMMARIZE_ENABLED": "false"}, Settings, ENV_PREFIX, NESTING
        )


def test_variables_without_the_prefix_are_not_the_services_business() -> None:
    assert unknown({"PATH": "x", "OTHER_APP_TOKEN": "y"}, KNOWN, ENV_PREFIX) == []


def test_the_example_file_names_only_settings_and_the_tooling() -> None:
    names = {
        line.lstrip("# ").split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if "=" in line and line.lstrip("# ").startswith(ENV_PREFIX)
    }
    assert names
    assert unknown(dict.fromkeys(names, ""), KNOWN, ENV_PREFIX) == []
