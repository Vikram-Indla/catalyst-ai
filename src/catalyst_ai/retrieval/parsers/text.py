"""Plain text and Markdown: headings become the path, paragraphs and list items become blocks."""

import re

from catalyst_ai.retrieval.parsers.port import (
    MAX_DEPTH,
    MAX_TEXT_CHARS,
    Block,
    Parsed,
    ParserError,
    Reason,
    clip_heading,
)

HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s{0,3}(```|~~~)")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_BYTES = 4 * MAX_TEXT_CHARS


def decode(payload: bytes) -> str:
    """Decode as UTF-8; a document that is not text, or is over the byte limit, is refused."""
    if len(payload) > MAX_BYTES:
        raise ParserError(Reason.TOO_LARGE, "the file is over the byte limit for text")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ParserError(Reason.MALFORMED, "the bytes are not UTF-8 text") from error
    if CONTROL.search(text):
        raise ParserError(Reason.MALFORMED, "the text carries control characters")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _paragraphs(lines: list[str]) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    for line in lines:
        if LIST_ITEM.match(line) and current:
            paragraphs.append(" ".join(current))
            current = []
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))
    return paragraphs


def parse_text(payload: bytes) -> Parsed:
    """Plain text: paragraphs separated by blank lines, no headings."""
    text = decode(payload)
    return Parsed([Block((), paragraph) for paragraph in _paragraphs(text.split("\n"))])


def _push(path: list[str], level: int, title: str) -> None:
    del path[level - 1 :]
    while len(path) < level - 1:
        path.append("")
    path.append(clip_heading(title))


def parse_markdown(payload: bytes) -> Parsed:
    """Markdown: `#` headings set the path (six levels at most); fenced code stays one block."""
    text = decode(payload)
    blocks: list[Block] = []
    path: list[str] = []
    pending: list[str] = []
    in_fence = False

    def flush() -> None:
        for paragraph in _paragraphs(pending):
            blocks.append(Block(tuple(h for h in path if h), paragraph))
        pending.clear()

    for line in text.split("\n"):
        if FENCE.match(line):
            in_fence = not in_fence
            pending.append("")
            continue
        heading = None if in_fence else HEADING.match(line)
        if heading is None:
            pending.append(line)
            continue
        flush()
        _push(path, min(len(heading.group(1)), MAX_DEPTH), heading.group(2))
    flush()
    return Parsed(blocks)
