"""The authored stand-ins for the assistant, the unfurl card and the chat summary.

The assistant stand-in answers the last turn from the numbered sources by word overlap, cites
each sentence it keeps, and says not found when nothing overlaps or the turn is an instruction —
the pipeline's rules are what the numbers prove, not a model's reading.
"""

import json
import re
from typing import Any

from tools.authored_documents import _instruction, _sentences, _supports
from tools.authored_envelope import envelope

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
NUMBERED = re.compile(r"^\[(?P<n>\d+)\] (?P<text>.*?)(?=\n\n\[\d+\] |\Z)", re.S | re.M)
TURN = re.compile(r"^(?P<role>user|assistant): (?P<text>.*)$", re.M)
FACT_STATUS = re.compile(r"^status: (?P<value>.+)$", re.M)
FACT_DATE = re.compile(r"\b(?P<value>\d{4}-\d{2}-\d{2})\b")
FACT_COUNT = re.compile(r"\b(?P<value>\d+ (?:rows|items|members|days|hours|pages))\b")
OFF_TOPIC = ("weather", "capital of", "recipe", "stock price", "write me a poem", "joke")
MARKER = "\n---\n"
MAX_SENTENCES = 2
MAX_SUMMARY_WORDS = 40
DECISION_CUES = ("agreed", "decided", "we will go with", "settled")
ACTION_CUES = ("i will", "i'll", "will take", "owns", "to do:")


def _turn(body: dict[str, Any]) -> str:
    return "".join(part.get("text", "") for part in body["contents"][0]["parts"])


def _fields(turn: str) -> dict[str, str]:
    return {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}


def _sources(text: str) -> list[tuple[int, str]]:
    return [(int(m.group("n")), m.group("text").strip()) for m in NUMBERED.finditer(text)]


def _question(thread: str) -> str:
    turns = [m.groupdict() for m in TURN.finditer(thread)]
    users = [t["text"] for t in turns if t["role"] == "user"]
    return users[-1] if users else ""


def _completion(prose: str, *, not_found: bool, rationale: str) -> str:
    return prose + MARKER + json.dumps({"not_found": not_found, "rationale": rationale})


HEAD = re.compile(r"^(?P<kind>[a-z_]+) (?P<key>[^:]+): (?P<title>.+)$")


def _facts(text: str) -> list[str]:
    """Return the sentences of one source: prose sentences, and the status as a sentence."""
    lines = text.splitlines()
    head = HEAD.match(lines[0]) if lines else None
    key = head.group("key") if head else ""
    facts: list[str] = []
    for line in lines[1:] if head else lines:
        if line.startswith("(") or line.startswith("page "):
            continue
        if line.startswith("status: ") and key:
            facts.append(f"The status of {key} is {line.removeprefix('status: ').strip()}.")
        else:
            facts += [s for s in _sentences(line) if not _instruction(s)]
    return facts


def answer_turn(body: dict[str, Any]) -> dict[str, Any]:
    """Cite the source sentences that overlap the last turn; otherwise say not found."""
    turn = _turn(body)
    fields = _fields(turn)
    question = _question(fields.get("thread", ""))
    lowered = question.lower()
    if _instruction(question) or any(cue in lowered for cue in OFF_TOPIC):
        prose = "I only help with work in this product, so I cannot answer that."
        return envelope(body, _completion(prose, not_found=True, rationale="Outside the product."))
    ranked: list[tuple[int, int, str]] = []
    for number, text in _sources(fields.get("sources", "")):
        for sentence in _facts(text):
            support = _supports(question, sentence, text)
            if support:
                ranked.append((support, number, sentence))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    kept: list[str] = []
    for _, number, sentence in ranked[:MAX_SENTENCES]:
        line = f"{sentence} [{number}]"
        if line not in kept:
            kept.append(line)
    if not kept:
        prose = "The sources I was given do not answer that."
        return envelope(body, _completion(prose, not_found=True, rationale="No overlap."))
    return envelope(
        body, _completion(" ".join(kept), not_found=False, rationale="The best-matching sources.")
    )


def answer_unfurl(body: dict[str, Any]) -> dict[str, Any]:
    """Summarise from the first sentence; facts from the status, a date, a count."""
    turn = _turn(body)
    fields = _fields(turn)
    title, text = fields.get("title", "").strip(), fields.get("text", "").strip()
    if _instruction(text):
        text = ""
    facts: list[dict[str, str]] = []
    status = FACT_STATUS.search(text)
    if status:
        facts.append({"label": "status", "value": status.group("value").strip()})
    date = FACT_DATE.search(text)
    if date:
        facts.append({"label": "date", "value": date.group("value")})
    count = FACT_COUNT.search(text)
    if count:
        facts.append({"label": "size", "value": count.group("value")})
    prose_lines = [line for line in text.splitlines() if not line.startswith("status:")]
    first = _sentences("\n".join(prose_lines))[:1]
    summary = " ".join((first[0] if first else title).split()[:MAX_SUMMARY_WORDS])
    output = {"summary": summary or title, "facts": facts, "rationale": "From the text alone."}
    return envelope(body, json.dumps(output, ensure_ascii=False))


def chat_sections(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Lay the messages out under the four headings by cue; a section may be empty."""
    activity = [f"{i['token']}: {_sentences(i['text'])[0]}" for i in items[-3:] if i["text"]]
    decisions = [
        f"{i['token']}: {i['text']}"
        for i in items
        if any(cue in i["text"].lower() for cue in DECISION_CUES)
    ]
    actions = [
        f"{i['token']}: {i['text']}"
        for i in items
        if any(cue in i["text"].lower() for cue in ACTION_CUES)
    ]
    questions = [f"{i['token']}: {i['text']}" for i in items if i["text"].rstrip().endswith("?")]
    return [
        {"heading": "activity", "lines": activity},
        {"heading": "decisions", "lines": decisions},
        {"heading": "actions", "lines": actions},
        {"heading": "questions", "lines": questions},
    ]
