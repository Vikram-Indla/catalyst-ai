"""The lexical queries: distinctive tokens OR-ed for an item, a member's words passed through."""

from catalyst_ai.retrieval.lexical import any_query, distinctive_tokens, web_query


def test_distinctive_tokens_drop_stop_words_short_tokens_and_repeats() -> None:
    tokens = distinctive_tokens("The login button is broken on the login page for users")
    assert tokens == ["login", "button", "broken", "page"]
    assert len(distinctive_tokens(" ".join(f"word{i}" for i in range(40)))) == 12


def test_any_query_quotes_each_token() -> None:
    query = any_query("Export board CSV")
    assert query.form == "any"
    assert query.text == "'export' | 'board' | 'csv'"
    assert any_query("a an the").text == ""


def test_web_query_strips_control_characters_only() -> None:
    query = web_query('"login button" \x00 CAT-12')
    assert query.form == "web"
    assert query.text == '"login button"   CAT-12'
