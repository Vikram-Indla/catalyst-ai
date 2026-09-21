"""Chunking: paragraphs packed into windows of the corpus size; long paragraphs cut with overlap."""

import re

from catalyst_ai.retrieval.corpora import CorpusSpec

PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
JOIN = "\n\n"


def _cut_long(paragraph: str, size: int, overlap: int) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(paragraph):
        end = min(len(paragraph), start + size)
        if end < len(paragraph):
            space = paragraph.rfind(" ", start + 1, end)
            end = space if space > start else end
        parts.append(paragraph[start:end].strip())
        if end >= len(paragraph):
            break
        start = max(end - overlap, start + 1)
    return [part for part in parts if part]


def _pack(pieces: list[str], size: int) -> list[str]:
    windows: list[str] = []
    current = ""
    for piece in pieces:
        candidate = piece if not current else current + JOIN + piece
        if len(candidate) <= size:
            current = candidate
        else:
            windows.append(current)
            current = piece
    if current:
        windows.append(current)
    return windows


def chunk(text: str, spec: CorpusSpec) -> list[str]:
    """Split a document into the corpus's windows; deterministic, order-preserving, no empties."""
    normalised = text.replace("\r\n", "\n").strip()
    if not normalised:
        return []
    paragraphs = [p.strip() for p in PARAGRAPH_BREAK.split(normalised) if p.strip()]
    pieces: list[str] = []
    for paragraph in paragraphs:
        pieces.extend(_cut_long(paragraph, spec.chunk_chars, spec.overlap_chars))
    return _pack(pieces, spec.chunk_chars)


def embedding_input(title: str | None, window: str) -> str:
    """Return what the model sees for a chunk: the title above the window, when there is one."""
    return f"{title.strip()}\n{window}" if title and title.strip() else window
