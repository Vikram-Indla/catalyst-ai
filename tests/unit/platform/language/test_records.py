"""The record rules: tokens found and refused, citations traced and refused."""

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language.records import (
    foreign_tokens,
    refuse_foreign_tokens,
    refuse_untraceable,
    tokens_in,
    untraceable,
)


def test_tokens_in_and_foreign_tokens() -> None:
    assert tokens_in("p1 said, p12 agreed; pineapple p9999x") == {"p1", "p12"}
    assert foreign_tokens("p1 and p3", ["p2"], {"p1", "p2"}) == {"p3"}
    refuse_foreign_tokens("p1", ["p2"], {"p1", "p2"}, "summary")
    with pytest.raises(Error) as caught:
        refuse_foreign_tokens("p1 and p3", [], {"p1"}, "summary")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE
    assert caught.value.details[0].code == "participant_not_in_thread"
    assert caught.value.details[0].field == "summary"


def test_untraceable_citations_are_details_and_refused() -> None:
    details = untraceable([("facts.0", "a"), ("facts.1", "zz"), ("x", "b")], {"a", "b"})
    assert [(d.field, d.message) for d in details] == [("facts.1", "zz")]
    assert details[0].code == "untraceable_entry"
    refuse_untraceable([("f", "a")], {"a"})
    with pytest.raises(Error) as caught:
        refuse_untraceable([("f", "a"), ("g", "q")], {"a"})
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].message == "q"
