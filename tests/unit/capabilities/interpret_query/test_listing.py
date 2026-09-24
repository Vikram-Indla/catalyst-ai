"""The list contract's rule: declared names only, the list's formats, Latin digits, never a guess."""

import pytest

from catalyst_ai.capabilities.interpret_query.listing import listing_lines, normalise
from catalyst_ai.contract.interpret_query import Listing

CYCLES = Listing.model_validate(
    {
        "filters": [
            {"param": "state", "type": "enum", "values": ["planned", "active", "closed"]},
            {"param": "startsOnFrom", "type": "date"},
            {"param": "startsAtFrom", "type": "datetime"},
            {"param": "size", "type": "number"},
        ],
        "sorts": ["-startsOn", "name"],
    }
)


def test_the_declaration_is_written_for_the_prompt_one_parameter_a_line() -> None:
    text = listing_lines(CYCLES)
    assert "- state (enum): planned | active | closed" in text
    assert "Sorts: -startsOn, name (the first is the default)" in text
    assert "Free-text search (q): no" in text


def test_values_take_the_lists_formats_and_latin_digits() -> None:
    kept, sort, problems = normalise(
        {"state": "ACTIVE", "startsOnFrom": "٢٠٢٦-١٠-٠١", "size": "۱۲"}, "-startsOn", CYCLES
    )
    assert kept == {"state": "active", "startsOnFrom": "2026-10-01", "size": "12"}
    assert sort == "-startsOn"
    assert problems == []


@pytest.mark.parametrize(
    ("parameters", "sort", "problem"),
    [
        ({"budget": "5"}, None, "param_not_declared: budget"),
        ({"state": "archived"}, None, "value_not_allowed: state"),
        ({"startsOnFrom": "1 October"}, None, "value_not_allowed: startsOnFrom"),
        ({"startsOnFrom": "2026-02-30"}, None, "value_not_allowed: startsOnFrom"),
        ({"startsAtFrom": "2026-10-01T00:00:00"}, None, "value_not_allowed: startsAtFrom"),
        ({"size": "twelve"}, None, "value_not_allowed: size"),
        ({"q": "portal"}, None, "param_not_declared: q"),
        ({}, "-requestedAt", "sort_not_declared: -requestedAt"),
    ],
    ids=[
        "undeclared field",
        "undeclared value",
        "a date in words",
        "an impossible date",
        "a date-time without offset",
        "a number in words",
        "search the list lacks",
        "undeclared sort",
    ],
)
def test_anything_the_list_does_not_declare_is_a_problem_never_a_neighbour(
    parameters: dict[str, str], sort: str | None, problem: str
) -> None:
    kept, _, problems = normalise(parameters, sort, CYCLES)
    assert problems == [problem]
    assert all(name not in kept for name in parameters if problem.endswith(name))


def test_free_text_goes_to_q_only_where_the_list_has_search() -> None:
    searchable = CYCLES.model_copy(update={"q": True})
    assert normalise({"q": "portal"}, None, searchable)[0] == {"q": "portal"}
