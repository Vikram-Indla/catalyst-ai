"""The config ledger equals the settings, including the settings `Settings` inherits in config/."""

from pathlib import Path

from tools.checks import config

SETTINGS = """
class Pins(BaseModel):
    model_text_default: str | None = None


class Settings(BaseSettings, Pins):
    model_config = None
    environment: str = "development"
"""


def test_a_setting_inherited_from_a_config_base_is_a_setting(tmp_path: Path) -> None:
    folder = tmp_path / "src" / "catalyst_ai" / "config"
    folder.mkdir(parents=True)
    (folder / "settings.py").write_text(SETTINGS, encoding="utf-8")
    assert config.settings_fields(tmp_path) == {"ENVIRONMENT", "MODEL_TEXT_DEFAULT"}


def test_the_repository_ledger_matches_its_settings() -> None:
    assert config.run(Path.cwd()) == []
