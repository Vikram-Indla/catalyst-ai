"""The parser port: every format yields blocks under a heading path, or a reason class."""

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

MAX_TEXT_CHARS = 200_000
MAX_BLOCKS = 5_000
MAX_DEPTH = 6
MAX_HEADING_CHARS = 200


class Reason(StrEnum):
    """Why a document was refused; the class the backend sees, never the file's content."""

    TOO_LARGE = "document_too_large"
    UNSUPPORTED = "document_unsupported"
    MALFORMED = "document_malformed"
    TIMEOUT = "document_timeout"
    RESTRICTED = "document_restricted"


class ParserError(Exception):
    """A document refused with its reason class; the message names the rule, never the bytes."""

    def __init__(self, reason: Reason, message: str) -> None:
        """Keep the reason class and a content-free message."""
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class Block:
    """One paragraph, list item, table row or slide text under the headings above it."""

    heading_path: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class Parsed:
    """What a parser yields: the blocks in reading order and the headings it saw."""

    blocks: list[Block] = field(default_factory=list)

    @property
    def headings(self) -> list[str]:
        """Return every distinct heading path joined with ` > `, in order of first appearance."""
        seen: dict[str, None] = {}
        for block in self.blocks:
            if block.heading_path:
                seen.setdefault(" > ".join(block.heading_path), None)
        return list(seen)

    @property
    def chars(self) -> int:
        """Return the text size of the document."""
        return sum(len(block.text) for block in self.blocks)


Parser = Callable[[bytes], Parsed]


def bound(parsed: Parsed) -> Parsed:
    """Refuse a parsed document over the block or text limits — the same limits everywhere."""
    if len(parsed.blocks) > MAX_BLOCKS or parsed.chars > MAX_TEXT_CHARS:
        raise ParserError(Reason.TOO_LARGE, "the document's text is over the limit")
    return parsed


def clip_heading(text: str) -> str:
    """Return the heading kept short and on one line."""
    return " ".join(text.split())[:MAX_HEADING_CHARS]
