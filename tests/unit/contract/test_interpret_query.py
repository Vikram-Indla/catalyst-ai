"""The interpret-query contract: the grammar as data, its bounds, the defaults."""

from datetime import datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.interpret_query import Grammar, GrammarField, InterpretQueryRequest

ORG = UUID("11111111-1111-7111-8111-111111111111")
FIELD = GrammarField(name="status", type="string", operators=["="], values=["Done"])


def _request(**overrides: object) -> InterpretQueryRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "text": "done items",
        "grammar": Grammar(fields=[FIELD]),
        "now": datetime.fromisoformat("2026-09-24T01:30:00+03:00"),
    }
    values.update(overrides)
    return InterpretQueryRequest.model_validate(values)


def test_the_defaults_are_riyadh_and_english() -> None:
    request = _request()
    assert request.timezone == "Asia/Riyadh"
    assert request.locale == "en"


def test_a_grammar_needs_a_field_and_a_field_an_operator_the_language_knows() -> None:
    with pytest.raises(ValidationError):
        Grammar(fields=[])
    with pytest.raises(ValidationError):
        GrammarField.model_validate({"name": "status", "type": "string", "operators": ["~="]})
    with pytest.raises(ValidationError):
        GrammarField.model_validate({"name": "1st", "type": "string", "operators": ["="]})


def test_the_sentence_the_locale_and_the_zone_are_bounded() -> None:
    with pytest.raises(ValidationError):
        _request(text="")
    with pytest.raises(ValidationError):
        _request(text="x" * 501)
    with pytest.raises(ValidationError):
        _request(locale="fr")
    with pytest.raises(ValidationError):
        _request(timezone="../etc/passwd")


def test_a_request_carries_a_grammar_or_a_list_declaration_exactly_one() -> None:
    listing = {"filters": [], "sorts": ["name"]}
    base = {
        "organization_id": "11111111-1111-7111-8111-111111111111",
        "capability_version": "1.1.0",
        "text": "themes by name",
        "now": "2026-09-24T01:30:00+03:00",
    }
    assert InterpretQueryRequest.model_validate({**base, "listing": listing}).grammar is None
    with pytest.raises(ValidationError):
        InterpretQueryRequest.model_validate(base)
    with pytest.raises(ValidationError):
        InterpretQueryRequest.model_validate(
            {
                **base,
                "listing": listing,
                "grammar": {"fields": [{"name": "x", "type": "string", "operators": ["="]}]},
            }
        )
