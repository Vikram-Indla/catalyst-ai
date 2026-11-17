"""The property tests' counts under the nightly profile `make nightly` runs by hand."""

from tests.conftest import NIGHTLY_FACTOR, examples


def test_a_property_test_keeps_its_own_count_outside_the_nightly() -> None:
    assert examples(60) == 60
    assert NIGHTLY_FACTOR > 1
