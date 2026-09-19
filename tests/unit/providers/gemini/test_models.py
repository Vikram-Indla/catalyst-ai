"""Register rows: cost from usage counts rounds up; every alias resolves to a known id."""

from catalyst_ai.providers.gemini.models import FLASH, KNOWN_IDS, REGISTER, ModelSpec
from catalyst_ai.providers.port import ModelAlias


def test_cost_rounds_up_to_a_micro_dollar() -> None:
    spec = ModelSpec("m", 300, 2_500, 1)
    assert spec.cost_micros(1_000, 1_000) == 2_800
    assert spec.cost_micros(1, 0) == 1
    assert spec.cost_micros(0, 0) == 0


def test_every_alias_has_a_known_row() -> None:
    assert set(REGISTER) == set(ModelAlias)
    assert all(spec.model_id in KNOWN_IDS for spec in REGISTER.values())
    assert REGISTER[ModelAlias.GRADER_DEFAULT] is FLASH
