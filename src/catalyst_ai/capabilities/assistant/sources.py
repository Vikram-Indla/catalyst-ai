"""The sources a turn may rest on, numbered for the prompt and resolved from the reply's markers.

Passages retrieved from the spaces, the items and the pages the backend supplied are one list:
`[1]`, `[2]`, … The model cites by number; a number that was never shown is untraceable.
"""

import re
from dataclasses import dataclass

from catalyst_ai.contract.assistant import Context, ContextItem, SourceKind, TurnSource
from catalyst_ai.contract.documents import Citation
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.retrieval import Passage, quote_for

MARKER = re.compile(r"\[(\d{1,3})\]")
SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+(?!\[)")
UNCITED = "uncited_claim"
UNTRACEABLE = "untraceable_entry"
MIN_FACT_WORDS = 6
ABSENT = "(none)"
HEADING_JOIN = " > "


@dataclass(frozen=True)
class Source:
    """One numbered source: a passage, an item or a page."""

    number: int
    kind: SourceKind
    source_id: str
    text: str
    passage: Passage | None = None


def _item_text(item: ContextItem) -> str:
    head = f"{item.kind} {item.key or item.id}: {item.title}"
    lines = [head, f"status: {item.status}" if item.status else "", item.summary or ""]
    return "\n".join(line for line in lines if line)


def number_sources(passages: list[Passage], context: Context) -> list[Source]:
    """Passages first in rank order, then the items, then the pages; numbered from one."""
    sources: list[Source] = []
    for passage in passages:
        path = HEADING_JOIN.join(passage.heading_path) or ABSENT
        text = f"({path})\n{passage.text}"
        sources.append(Source(len(sources) + 1, "passage", passage.chunk_id, text, passage))
    for item in context.items:
        sources.append(Source(len(sources) + 1, "item", item.id, _item_text(item)))
    for page in context.pages:
        head = f"page {page.id}: {page.title}" if page.title else f"page {page.id}"
        sources.append(Source(len(sources) + 1, "page", page.id, f"{head}\n{page.text}"))
    return sources


def sources_text(sources: list[Source]) -> str:
    """Every source as the prompt reads it: `[n]` then its text, blank-line separated."""
    return "\n\n".join(f"[{s.number}] {s.text}" for s in sources)


def markers_of(reply: str) -> list[int]:
    """Return the numbers the reply cites, in order of first appearance."""
    return list(dict.fromkeys(int(m.group(1)) for m in MARKER.finditer(reply)))


def _is_factual(sentence: str) -> bool:
    words = MARKER.sub("", sentence).split()
    return len(words) >= MIN_FACT_WORDS and not sentence.rstrip().endswith(("?", "؟"))


def check_reply(reply: str, sources: list[Source], *, not_found: bool) -> None:
    """When sources were shown, every factual sentence cites one of them; unknown numbers refuse."""
    known = {s.number for s in sources}
    unknown = [n for n in markers_of(reply) if n not in known]
    if unknown:
        details = [ErrorDetail(field="reply", code=UNTRACEABLE, message=str(n)) for n in unknown]
        raise Error(
            ErrorCode.OUTPUT_INVALID, "the reply cites a source it was not shown", details=details
        )
    if not sources or not_found:
        return
    uncited = [
        ErrorDetail(field=f"reply.{i}", code=UNCITED, message="a factual sentence cites nothing")
        for i, sentence in enumerate(SENTENCE_END.split(reply.strip()))
        if _is_factual(sentence) and not MARKER.search(sentence)
    ]
    if uncited:
        raise Error(ErrorCode.OUTPUT_INVALID, "a reply sentence cites nothing", details=uncited)


def sources_cited(reply: str, sources: list[Source]) -> list[TurnSource]:
    """Resolve the reply's markers, in order of first use; a passage carries its citation."""
    by_number = {s.number: s for s in sources}
    cited: list[TurnSource] = []
    for number in markers_of(reply):
        source = by_number[number]
        citation = None
        if source.passage is not None:
            passage = source.passage
            citation = Citation(
                chunk_id=passage.chunk_id,
                document_id=passage.document_id,
                position=passage.position,
                heading_path=passage.heading_path,
                quote=quote_for(passage, reply),
            )
        cited.append(
            TurnSource(
                marker=number, kind=source.kind, source_id=source.source_id, citation=citation
            )
        )
    return cited
