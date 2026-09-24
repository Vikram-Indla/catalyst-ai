"""Register rows: cost from usage counts rounds up; every available alias resolves to a known id."""

from catalyst_ai.contract.models import UNAVAILABLE
from catalyst_ai.providers.gemini.models import (
    EMBEDDING,
    FLASH,
    KNOWN_IDS,
    REGISTER,
    UNVERIFIED_IN_REGION,
    ModelSpec,
)
from catalyst_ai.providers.port import ModelAlias


def test_cost_rounds_up_to_a_micro_dollar() -> None:
    spec = ModelSpec("m", 300, 2_500, 1)
    assert spec.cost_micros(1_000, 1_000) == 2_800
    assert spec.cost_micros(1, 0) == 1
    assert spec.cost_micros(0, 0) == 0


def test_every_available_alias_has_a_known_row_and_an_unavailable_one_has_none() -> None:
    assert set(REGISTER) == set(ModelAlias) - {ModelAlias(alias.value) for alias in UNAVAILABLE}
    assert ModelAlias.TEXT_LONG not in REGISTER
    assert all(spec.model_id in KNOWN_IDS for spec in REGISTER.values())


def test_both_text_rows_are_the_one_reachable_model_and_it_does_not_think() -> None:
    assert REGISTER[ModelAlias.TEXT_DEFAULT] is FLASH
    assert REGISTER[ModelAlias.TEXT_FAST] is FLASH
    assert FLASH.thinking_level == "minimal"
    assert FLASH.context_tokens == 1_048_576


def test_the_grader_is_the_text_row_it_measures_against() -> None:
    assert REGISTER[ModelAlias.GRADER_DEFAULT] is FLASH


def test_the_index_keeps_its_model() -> None:
    assert REGISTER[ModelAlias.EMBED_DEFAULT] is EMBEDDING
    assert EMBEDDING.thinking_level is None


def test_every_row_stays_unverified_in_region_until_the_model_list_is_read() -> None:
    assert {spec.residency for spec in REGISTER.values()} == {UNVERIFIED_IN_REGION}
