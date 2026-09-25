"""A model pinned by the environment: a priced id starts, any other refuses the start by name."""

from pathlib import Path

import pytest

from catalyst_ai import cli
from catalyst_ai.config.settings import ENV_PREFIX
from catalyst_ai.providers.gemini.models import FLASH
from tests.unit.config.test_kill_switch_names import base_environment

ROOT = Path(__file__).resolve().parents[3]


def test_check_accepts_a_priced_pin(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}MODEL_TEXT_DEFAULT", FLASH.model_id)
    assert cli.check(ROOT, load=True) == cli.EXIT_OK
    assert "settings valid" in capsys.readouterr().out


def test_check_and_serve_refuse_an_unpriced_pin_naming_the_variable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    base_environment(monkeypatch)
    monkeypatch.setenv(f"{ENV_PREFIX}MODEL_TEXT_FAST", f"{FLASH.model_id}-preview")
    assert cli.check(ROOT, load=True) == cli.EXIT_FAIL
    assert f"{ENV_PREFIX}MODEL_TEXT_FAST" in capsys.readouterr().out
    assert cli.main(["serve"]) == cli.EXIT_FAIL
    assert "serve: CATALYST_AI_MODEL_TEXT_FAST" in capsys.readouterr().out
