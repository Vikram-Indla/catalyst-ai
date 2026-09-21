"""Parsers per format behind one port: bytes in, blocks with a heading path out, or a reason."""

from types import MappingProxyType

from catalyst_ai.retrieval.parsers.office import parse_docx, parse_pptx
from catalyst_ai.retrieval.parsers.pdf import parse_pdf
from catalyst_ai.retrieval.parsers.port import (
    MAX_BLOCKS,
    MAX_DEPTH,
    MAX_TEXT_CHARS,
    Block,
    Parsed,
    Parser,
    ParserError,
    Reason,
    bound,
)
from catalyst_ai.retrieval.parsers.text import parse_markdown, parse_text

PARSERS: MappingProxyType[str, Parser] = MappingProxyType(
    {
        "docx": parse_docx,
        "pptx": parse_pptx,
        "pdf": parse_pdf,
        "markdown": parse_markdown,
        "text": parse_text,
    }
)


def parse(fmt: str, payload: bytes) -> Parsed:
    """Parse the payload as the declared format; an unknown format is `document_unsupported`."""
    parser = PARSERS.get(fmt)
    if parser is None:
        raise ParserError(Reason.UNSUPPORTED, "no parser for the declared format")
    return bound(parser(payload))


__all__ = [
    "MAX_BLOCKS",
    "MAX_DEPTH",
    "MAX_TEXT_CHARS",
    "PARSERS",
    "Block",
    "Parsed",
    "ParserError",
    "Reason",
    "parse",
]
