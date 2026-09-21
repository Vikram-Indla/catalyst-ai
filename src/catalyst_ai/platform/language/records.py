"""Rules for outputs that become records: every entry traced to a source, people only by token."""

import re
from collections.abc import Iterable

from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error

TOKEN = re.compile(r"\bp[0-9]{1,4}\b")
UNTRACEABLE = "untraceable_entry"
PARTICIPANT_LEAK = "participant_not_in_thread"


def tokens_in(text: str) -> set[str]:
    """Every participant token a text names."""
    return set(TOKEN.findall(text))


def foreign_tokens(text: str, named: Iterable[str], known: set[str]) -> set[str]:
    """Tokens named in the text or the list that the data did not carry."""
    return (tokens_in(text) | set(named)) - known


def refuse_foreign_tokens(text: str, named: Iterable[str], known: set[str], where: str) -> None:
    """Raise `ai.output.unsafe` when the output names a participant the data did not."""
    foreign = foreign_tokens(text, named, known)
    if foreign:
        detail = ErrorDetail(
            field=where, code=PARTICIPANT_LEAK, message=f"{len(foreign)} unknown token(s)"
        )
        raise Error(
            ErrorCode.OUTPUT_UNSAFE,
            "the output names a participant outside the data",
            details=[detail],
        )


def untraceable(cited: Iterable[tuple[str, str]], sources: set[str]) -> list[ErrorDetail]:
    """One detail per (field, id) pair whose id is not a supplied source id."""
    return [
        ErrorDetail(field=field, code=UNTRACEABLE, message=source_id)
        for field, source_id in cited
        if source_id not in sources
    ]


def refuse_untraceable(cited: Iterable[tuple[str, str]], sources: set[str]) -> None:
    """Raise `ai.output.invalid` when an entry cites an id the request did not carry."""
    details = untraceable(cited, sources)
    if details:
        raise Error(
            ErrorCode.OUTPUT_INVALID,
            "an entry cites a source the request did not carry",
            details=details,
        )
