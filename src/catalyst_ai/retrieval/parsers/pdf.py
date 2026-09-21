"""PDF through `pypdf`: the text layer per page, after the script and size guards; no OCR."""

import io
import re

from pypdf import PdfReader

from catalyst_ai.retrieval.parsers.port import Block, Parsed, ParserError, Reason, clip_heading

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 500
SCRIPT_MARKERS = (b"/JavaScript", b"/JS", b"/Launch", b"/OpenAction", b"/AA", b"/EmbeddedFile")
MAGIC = b"%PDF-"
PARAGRAPH = re.compile(r"\n\s*\n")


def guard(payload: bytes) -> None:
    """Refuse before parsing: not a PDF, over the byte limit, or carrying scripts or actions."""
    if len(payload) > MAX_BYTES:
        raise ParserError(Reason.TOO_LARGE, "the file is over the byte limit for PDF")
    if not payload.startswith(MAGIC):
        raise ParserError(Reason.MALFORMED, "the bytes are not a PDF")
    if any(marker in payload for marker in SCRIPT_MARKERS):
        raise ParserError(Reason.MALFORMED, "the document carries scripts or actions")


def _reader(payload: bytes) -> PdfReader:
    try:
        reader = PdfReader(io.BytesIO(payload), strict=False)
        count = len(reader.pages)
    except Exception as error:
        raise ParserError(Reason.MALFORMED, "the PDF could not be read") from error
    if count > MAX_PAGES:
        raise ParserError(Reason.TOO_LARGE, "the document has too many pages")
    return reader


def _pages(payload: bytes) -> list[str]:
    try:
        return [page.extract_text() or "" for page in _reader(payload).pages]
    except ParserError:
        raise
    except Exception as error:
        raise ParserError(Reason.MALFORMED, "a page could not be read") from error


def parse_pdf(payload: bytes) -> Parsed:
    """One heading per page; paragraphs of the page's text layer become blocks."""
    guard(payload)
    blocks: list[Block] = []
    for number, text in enumerate(_pages(payload), start=1):
        heading = clip_heading(f"Page {number}")
        for paragraph in PARAGRAPH.split(text):
            words = " ".join(paragraph.split())
            if words:
                blocks.append(Block((heading,), words))
    return Parsed(blocks)
