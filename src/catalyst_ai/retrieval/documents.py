"""Documents in the index: structure-aware windows, keys per space, passages with provenance."""

import re
from dataclasses import dataclass

from catalyst_ai.contract.documents import MAX_QUOTE
from catalyst_ai.retrieval.chunking import chunk
from catalyst_ai.retrieval.corpora import CorpusSpec
from catalyst_ai.retrieval.parsers import Block, Parsed

HEADING_MARK = "§ "
HEADING_JOIN = " > "
KEY_JOIN = "/"
CHUNK_JOIN = "#"
BLOCK_JOIN = "\n\n"
HEADING_LINE = re.compile(r"^§ (?P<path>.*)\n")


def document_key(space_id: str, document_id: str) -> str:
    """Return the index key of a document: the space first, so a space is a prefix."""
    return f"{space_id}{KEY_JOIN}{document_id}"


def space_prefix(space_id: str) -> str:
    """Return the prefix every key of a space starts with."""
    return f"{space_id}{KEY_JOIN}"


def chunk_id(key: str, position: int) -> str:
    """Return the id a citation names: the document's key and the window's position."""
    return f"{key}{CHUNK_JOIN}{position}"


def _groups(blocks: list[Block]) -> list[tuple[tuple[str, ...], str]]:
    groups: list[tuple[tuple[str, ...], list[str]]] = []
    for block in blocks:
        if groups and groups[-1][0] == block.heading_path:
            groups[-1][1].append(block.text)
        else:
            groups.append((block.heading_path, [block.text]))
    return [(path, BLOCK_JOIN.join(texts)) for path, texts in groups]


def windows_of(parsed: Parsed, spec: CorpusSpec) -> list[str]:
    """Cut each run of blocks under one heading path into windows, each led by its path."""
    windows: list[str] = []
    for path, text in _groups(parsed.blocks):
        lead = HEADING_MARK + HEADING_JOIN.join(path) + "\n" if path else ""
        windows.extend(lead + window for window in chunk(text, spec))
    return windows


def split_window(window: str) -> tuple[list[str], str]:
    """Return the heading path a window leads with and the text after it."""
    match = HEADING_LINE.match(window)
    if match is None:
        return [], window
    return match.group("path").split(HEADING_JOIN), window[match.end() :]


@dataclass(frozen=True)
class Passage:
    """One retrieved window with everything a citation needs."""

    chunk_id: str
    document_id: str
    position: int
    heading_path: list[str]
    text: str
    score: float


def passage_of(key: str, position: int, window: str, score: float) -> Passage:
    """Turn a stored window back into a passage: split the key and the heading line."""
    heading_path, text = split_window(window)
    document_id = key.split(KEY_JOIN, 1)[1] if KEY_JOIN in key else key
    return Passage(chunk_id(key, position), document_id, position, heading_path, text, score)


def quote_for(passage: Passage, claim: str) -> str:
    """Return the passage's opening words; the part the claim rests on is not guessed at."""
    del claim
    words = passage.text.split()
    quote = ""
    for word in words:
        if len(quote) + len(word) + 1 > MAX_QUOTE:
            break
        quote = f"{quote} {word}".strip()
    return quote or passage.text[:MAX_QUOTE]
