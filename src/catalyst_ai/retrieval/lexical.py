"""The lexical leg's queries: an OR of an item's distinctive tokens, or a member's own words."""

import re

from catalyst_ai.platform.storage import LexicalQuery

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "when",
        "then",
        "into",
        "have",
        "are",
        "was",
        "not",
        "can",
        "should",
        "user",
        "users",
    }
)
MIN_TOKEN = 3
ANY_TOKENS = 12
FORM_ANY = "any"
FORM_WEB = "web"


def distinctive_tokens(text: str, limit: int = ANY_TOKENS) -> list[str]:
    """Lower-cased tokens of at least three characters, stop words out, first seen first."""
    seen: list[str] = []
    for token in TOKEN.findall(text.lower()):
        if len(token) >= MIN_TOKEN and token not in STOP and token not in seen:
            seen.append(token)
        if len(seen) == limit:
            break
    return seen


def any_query(text: str) -> LexicalQuery:
    """Match chunks holding any of the item's distinctive tokens (the `similar` mode)."""
    tokens = distinctive_tokens(text)
    return LexicalQuery(FORM_ANY, " | ".join(f"'{token}'" for token in tokens))


def web_query(text: str) -> LexicalQuery:
    """Pass a member's words to the text search's web-style parser (the `query` mode)."""
    return LexicalQuery(FORM_WEB, CONTROL.sub(" ", text).strip())
