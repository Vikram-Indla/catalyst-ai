"""The query language against a grammar sent as data: what parses, what is refused, what is equal."""

import pytest

from catalyst_ai.capabilities.interpret_query.grammar import GrammarError, canonical
from tests.unit.capabilities.interpret_query.conftest import GRAMMAR


def test_a_plain_query_is_written_back_canonically() -> None:
    written = canonical('assignee = currentUser() and status = "to do"', GRAMMAR)
    assert written == 'assignee = currentUser() AND status = "To Do"'


def test_and_or_operands_and_in_lists_are_ordered_so_equal_queries_compare_equal() -> None:
    first = canonical('status in ("Done", "To Do") and issuetype = Bug', GRAMMAR)
    second = canonical('issuetype = "bug" AND status IN ("to do", done)', GRAMMAR)
    assert first == second


def test_every_operator_the_card_names_parses() -> None:
    query = (
        'priority >= High and not (status was "Done") and assignee is empty '
        "and labels not in (backend) and status changed and reporter is not null "
        "and created >= -7d and duedate < 2026-10-01 order by created desc, priority"
    )
    written = canonical(query, GRAMMAR)
    assert written.endswith("ORDER BY created DESC, priority ASC")
    assert "assignee IS EMPTY" in written
    assert 'NOT (status WAS "Done")' in written


def test_was_not_is_one_operator() -> None:
    assert canonical("status was not Done", GRAMMAR) == 'status WAS NOT "Done"'


@pytest.mark.parametrize(
    ("query", "problem"),
    [
        ("colour = red", "unknown_field: colour"),
        ("status > Done", "operator_not_allowed: status >"),
        ("status = Shipped", "value_not_allowed: status Shipped"),
        ("created = yesterday", "value_not_allowed: created yesterday"),
        ("storypoints = many", "value_not_allowed: storypoints many"),
        ("assignee = openSprints()", "value_not_allowed: assignee openSprints()"),
        ("order by colour", "unknown_field: colour"),
        ("status = Done and", "unknown_field: "),
        ("", "syntax: empty query"),
    ],
)
def test_what_the_grammar_does_not_allow_is_refused_with_its_reason(
    query: str, problem: str
) -> None:
    with pytest.raises(GrammarError) as caught:
        canonical(query, GRAMMAR)
    assert any(found.startswith(problem) for found in caught.value.problems), caught.value.problems


def test_a_stray_character_is_a_syntax_problem_not_a_crash() -> None:
    with pytest.raises(GrammarError) as caught:
        canonical('status = "Done', GRAMMAR)
    assert caught.value.problems[0].startswith("syntax")


def test_an_order_alone_is_a_query() -> None:
    assert canonical("ORDER BY updated DESC", GRAMMAR) == "ORDER BY updated DESC"
