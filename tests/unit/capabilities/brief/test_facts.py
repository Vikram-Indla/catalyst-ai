"""The chain as the model reads it: ids first, "not measured" written out, numbers in both scripts."""

from catalyst_ai.capabilities.brief.facts import (
    ids_of,
    is_empty,
    numbers_in,
    render,
    unseen_numbers,
)
from catalyst_ai.contract.brief import Chain
from tests.unit.capabilities.brief.conftest import brief_request


def test_every_fact_is_one_line_led_by_its_id_and_not_measured_is_written_out() -> None:
    text = render(brief_request().chain)
    assert "objective [O-1] status at_risk, progress 35%: Online renewal" in text
    assert "key result [KR-1] value 42 %, target 80 %: Online share" in text
    assert "key result [KR-2] value not measured, target 4.5: Satisfaction" in text
    assert "project [P-1] delivery health off_track, strategic health on_track, blocked" in text
    assert ids_of(brief_request().chain) == {"T-1", "O-1", "KR-1", "KR-2", "P-1", "F-1"}


def test_a_number_counts_as_seen_by_value_in_either_script() -> None:
    chain = brief_request().chain
    assert numbers_in("٣٥٪ and 4.50") == {35.0, 4.5}
    assert unseen_numbers("at ٣٥ percent, target 80", chain) == set()
    assert unseen_numbers("about 100% soon, 3 projects", chain) == {100.0, 3.0}


def test_a_chain_with_only_a_theme_is_empty() -> None:
    chain = Chain.model_validate({"theme": {"id": "T-1", "title": "t"}})
    assert is_empty(chain)
    assert not is_empty(brief_request().chain)
