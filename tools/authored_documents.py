"""The authored stand-ins for grounded answers and drafts: overlap-ranked, cited, disclosed."""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
PASSAGE = re.compile(
    r"^\[(?P<id>[^\]]+)\] \((?P<path>[^)]*)\)\n(?P<text>.*?)(?=\n\n\[|\Z)", re.S | re.M
)
SOURCE = re.compile(
    r"^\[(?P<id>[^\]]+)\](?P<title>[^\n]*)\n(?P<text>.*?)(?=\n\n\[|\Z)", re.S | re.M
)
WORD = re.compile(r"[^\W\d_]{3,}")
STOP = frozenset(
    {
        "happens",
        "happen",
        "appear",
        "appears",
        "much",
        "many",
        "long",
        "often",
        "the",
        "and",
        "for",
        "with",
        "what",
        "when",
        "who",
        "where",
        "how",
        "does",
        "which",
        "are",
        "is",
        "a",
        "an",
        "of",
        "to",
        "in",
        "on",
        "at",
        "from",
        "by",
    }
)
INSTRUCTION_CUES = ("ignore", "you are now", "<<<", "reveal", "system prompt", "access granted")
MIN_OVERLAP = 2
STEM = 4
SHORT = 3
LONG_WORD = 6
MAX_CLAIMS = 3
MAX_SOURCE_WORDS = 40


def _turn(body: dict[str, Any]) -> str:
    return "".join(part.get("text", "") for part in body["contents"][0]["parts"])


def _fields(turn: str) -> dict[str, str]:
    return {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}


def _stem(word: str) -> str:
    lowered = word.lower()
    if len(lowered) > SHORT and lowered.endswith("s"):
        lowered = lowered[:-1]
    return lowered[:STEM]


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in WORD.findall(text) if w.lower() not in STOP}


def _required(text: str) -> set[str]:
    return {_stem(w) for w in WORD.findall(text) if len(w) >= LONG_WORD and w.lower() not in STOP}


def _supports(question: str, sentence: str, passage: str) -> int:
    """Count the question stems the sentence carries; zero unless the passage has each long word."""
    asked, present = _stems(question), _stems(sentence)
    if not _required(question) <= _stems(passage):
        return 0
    overlap = len(asked & present)
    return overlap if overlap >= min(MIN_OVERLAP, len(asked)) else 0


def _instruction(text: str) -> bool:
    lowered = text.lower()
    return any(cue in lowered for cue in INSTRUCTION_CUES)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]


def answer_ask(body: dict[str, Any]) -> dict[str, Any]:
    """Rank the passages by word overlap with the question; cite the best; refuse to guess."""
    turn = _turn(body)
    fields = _fields(turn)
    question = fields.get("question", "")
    ranked: list[tuple[int, str, str]] = []
    for match in PASSAGE.finditer(fields.get("passages", "")):
        text = match.group("text").strip()
        if _instruction(text):
            continue
        for sentence in _sentences(text):
            support = _supports(question, sentence, text)
            if support:
                ranked.append((support, match.group("id"), sentence))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    claims: list[dict[str, Any]] = []
    for _, chunk, sentence in ranked[:MAX_CLAIMS]:
        if sentence not in [c["text"] for c in claims]:
            claims.append({"text": sentence, "chunk_ids": [chunk]})
    if not claims or _instruction(question):
        output: dict[str, Any] = {
            "claims": [],
            "not_found": True,
            "rationale": "No passage states an answer to the question.",
        }
    else:
        output = {"claims": claims, "not_found": False, "rationale": "The best-matching passages."}
    return envelope(body, json.dumps(output, ensure_ascii=False))


def answer_draft(body: dict[str, Any]) -> dict[str, Any]:
    """One section per source that says something, its opening words, cited to the source."""
    turn = _turn(body)
    fields = _fields(turn)
    sections = []
    for match in SOURCE.finditer(fields.get("passages", "")):
        text = match.group("text").strip()
        lines = [
            line
            for line in text.splitlines()
            if line.strip() and not line.startswith("#") and not _instruction(line)
        ]
        words = " ".join(lines).split()
        if len(words) < MAX_SOURCE_WORDS // 4:
            continue
        heading = match.group("title").strip() or match.group("id")
        sections.append(
            {
                "heading": heading,
                "text": " ".join(words[:MAX_SOURCE_WORDS]),
                "sources": [match.group("id")],
            }
        )
    if not sections:
        output: dict[str, Any] = {
            "title": "",
            "sections": [],
            "empty_reason": "sources_insufficient",
            "rationale": "The sources carry too little to draft from.",
        }
    else:
        output = {
            "title": "Guide",
            "sections": sections,
            "empty_reason": None,
            "rationale": "One section per source, in the sources' own words.",
        }
    return envelope(body, json.dumps(output, ensure_ascii=False))


def answer_documents(body: dict[str, Any]) -> dict[str, Any]:
    """Dispatch on the mode section: claims for an answer, sections for a draft."""
    turn = _turn(body)
    return answer_ask(body) if 'Fill "claims"' in turn else answer_draft(body)
