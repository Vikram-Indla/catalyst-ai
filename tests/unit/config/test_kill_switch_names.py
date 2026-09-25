"""Each capability's kill switch, as its descriptor names it, is a variable the settings read."""

import os
from pathlib import Path

import pytest

from catalyst_ai.capabilities import summarize
from catalyst_ai.config import Settings, load_settings
from catalyst_ai.config.settings import ENV_PREFIX, NESTING
from catalyst_ai.config.unknown import declared
from tools import origin

ROOT = Path(__file__).resolve().parents[3]
KNOWN = declared(Settings, ENV_PREFIX, NESTING)


def base_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [n for n in os.environ if n.upper().startswith(ENV_PREFIX)]:
        monkeypatch.delenv(name)
    monkeypatch.setenv(f"{ENV_PREFIX}ENVIRONMENT", "development")
    monkeypatch.setenv(f"{ENV_PREFIX}AUTH_PUBLIC_KEYS", origin.PUBLIC_KEYS)
    monkeypatch.setenv(f"{ENV_PREFIX}DATABASE_URL", "postgresql://serve:p@h/d")


def test_each_descriptors_kill_switch_is_a_name_the_settings_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv(summarize.descriptor.kill_switch, "false")
    assert load_settings(os.environ).capability_summarize.enabled is False
    switches = {
        line.split('"')[1]
        for path in (ROOT / "src/catalyst_ai/capabilities").glob("*/descriptor.py")
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("kill_switch")
    }
    assert len(switches) >= 14
    assert switches <= KNOWN
