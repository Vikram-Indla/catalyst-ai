"""Word and PowerPoint: a zip of XML read with the bomb, macro and entity guards up front."""

import io
import re
import zipfile
from collections.abc import Iterator
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from catalyst_ai.retrieval.parsers.port import (
    MAX_DEPTH,
    Block,
    Parsed,
    ParserError,
    Reason,
    clip_heading,
)

MAX_ENTRIES = 2_000
MAX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_RATIO = 100
MACRO_MARKERS = ("vbaproject", "macros/", ".bin")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
HEADING_STYLE = re.compile(r"^(?:heading|title)\s*(\d)?$", re.I)
SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
DOCUMENT_PART = "word/document.xml"


def open_zip(payload: bytes) -> zipfile.ZipFile:
    """Open the container and refuse it before reading any entry when its shape is hostile."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
        entries = archive.infolist()
    except zipfile.BadZipFile as error:
        raise ParserError(Reason.MALFORMED, "the bytes are not a zip container") from error
    if len(entries) > MAX_ENTRIES:
        raise ParserError(Reason.TOO_LARGE, "the container has too many entries")
    total = 0
    for entry in entries:
        lowered = entry.filename.lower()
        if ".." in lowered or lowered.startswith("/"):
            raise ParserError(Reason.MALFORMED, "an entry escapes the container")
        if any(marker in lowered for marker in MACRO_MARKERS):
            raise ParserError(Reason.MALFORMED, "the document carries macros or binaries")
        total += entry.file_size
        compressed = max(entry.compress_size, 1)
        if entry.file_size > MAX_ENTRY_BYTES or entry.file_size // compressed > MAX_RATIO:
            raise ParserError(Reason.TOO_LARGE, "an entry inflates beyond the limit")
    if total > MAX_TOTAL_BYTES:
        raise ParserError(Reason.TOO_LARGE, "the container inflates beyond the limit")
    return archive


def read_xml(archive: zipfile.ZipFile, name: str) -> Element:
    """Read one XML part with entities and DTDs forbidden."""
    try:
        with archive.open(name) as part:
            root: Element = ElementTree.parse(part).getroot()
    except KeyError as error:
        raise ParserError(Reason.MALFORMED, "a required part is missing") from error
    except Exception as error:
        raise ParserError(Reason.MALFORMED, "a part is not well-formed XML") from error
    return root


def _runs(element: Element, tag: str) -> str:
    return " ".join(" ".join((t.text or "").split()) for t in element.iter(tag)).strip()


def _heading_level(paragraph: Element) -> int | None:
    style = paragraph.find(f"{W}pPr/{W}pStyle")
    if style is None:
        return None
    match = HEADING_STYLE.match(style.get(f"{W}val", ""))
    if match is None:
        return None
    return min(int(match.group(1) or 1), MAX_DEPTH)


def _push(path: list[str], level: int, title: str) -> None:
    del path[level - 1 :]
    while len(path) < level - 1:
        path.append("")
    path.append(clip_heading(title))


def parse_docx(payload: bytes) -> Parsed:
    """Word: every paragraph a block; heading styles set the path; tables read row by row."""
    root = read_xml(open_zip(payload), DOCUMENT_PART)
    blocks: list[Block] = []
    path: list[str] = []
    for paragraph in root.iter(f"{W}p"):
        text = _runs(paragraph, f"{W}t")
        if not text:
            continue
        level = _heading_level(paragraph)
        if level is not None:
            _push(path, level, text)
            continue
        blocks.append(Block(tuple(h for h in path if h), text))
    return Parsed(blocks)


def _slides(archive: zipfile.ZipFile) -> Iterator[tuple[int, Element]]:
    numbered = []
    for name in archive.namelist():
        match = SLIDE.match(name)
        if match:
            numbered.append((int(match.group(1)), name))
    for number, name in sorted(numbered):
        yield number, read_xml(archive, name)


def _is_title(shape: Element) -> bool:
    placeholder = shape.find(f"{P}nvSpPr/{P}nvPr/{P}ph")
    return placeholder is not None and placeholder.get("type", "") in {"title", "ctrTitle"}


def parse_pptx(payload: bytes) -> Parsed:
    """PowerPoint: one heading per slide from its title; every text paragraph a block under it."""
    archive = open_zip(payload)
    blocks: list[Block] = []
    for number, root in _slides(archive):
        shapes = list(root.iter(f"{P}sp"))
        titles = [_runs(s, f"{A}t") for s in shapes if _is_title(s)]
        heading = clip_heading(
            f"Slide {number}" + (f": {titles[0]}" if titles and titles[0] else "")
        )
        for shape in shapes:
            if _is_title(shape):
                continue
            for paragraph in shape.iter(f"{A}p"):
                text = _runs(paragraph, f"{A}t")
                if text:
                    blocks.append(Block((heading,), text))
    return Parsed(blocks)
