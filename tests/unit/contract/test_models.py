"""The alias vocabulary: what a capability may ask for, and the subset an environment may pick."""

from catalyst_ai.contract.models import ModelAlias, TextAlias


def test_every_alias_a_capability_may_ask_for() -> None:
    assert {alias.value for alias in ModelAlias} == {
        "text-default",
        "text-fast",
        "text-long",
        "embed-default",
        "grader-default",
    }


def test_an_environment_may_select_text_rows_only() -> None:
    selectable = {alias.value for alias in TextAlias}
    assert selectable == {"text-default", "text-fast", "text-long"}
    assert selectable < {alias.value for alias in ModelAlias}
    assert ModelAlias.EMBED_DEFAULT.value not in selectable
    assert ModelAlias.GRADER_DEFAULT.value not in selectable
    assert ModelAlias(TextAlias.TEXT_FAST.value) is ModelAlias.TEXT_FAST
