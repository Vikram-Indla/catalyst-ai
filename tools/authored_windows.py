"""The authored stand-in for standups and digests: cue-split updates, kind-grouped changes."""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

THREAD_LINE = re.compile(
    r"^\[(?P<id>[^\]]+)\] (?P<token>p\d+)(?: \((?P<kind>[a-z_]+)\))? @ (?P<at>\S+): (?P<text>.*)$"
)
CUES = (
    ("done", ("Done:", "أنجزت:")),
    ("doing", ("Doing:", "أعمل على:")),
    ("blocked", ("Blocked:", "معطل:")),
)
CUE_PATTERN = re.compile(r"(Done:|Doing:|Blocked:|أنجزت:|أعمل على:|معطل:)")
ARABIC_LETTER = re.compile(r"[؀-ۿ]")
LATIN_LETTER = re.compile(r"[A-Za-z]")


def items_of(body: str) -> list[dict[str, str]]:
    """Parse the fenced thread back into items; a line that is not an item is ignored."""
    items = []
    for line in body.splitlines():
        match = THREAD_LINE.match(line)
        if match:
            items.append({k: v or "" for k, v in match.groupdict().items()})
    return items


def _bucket(cue: str) -> str:
    return next(name for name, cues in CUES if cue in cues)


def split_update(text: str) -> dict[str, list[str]]:
    """Cut one update into its done, doing and blocked parts by cue; uncued text is dropped."""
    parts: dict[str, list[str]] = {"done": [], "doing": [], "blocked": []}
    pieces = CUE_PATTERN.split(text)
    for cue, piece in zip(pieces[1::2], pieces[2::2], strict=True):
        line = first_sentence(piece)
        if line:
            parts[_bucket(cue)].append(line)
    return parts


def first_sentence(text: str) -> str:
    """Return the first sentence without its full stop; a later sentence is left out."""
    return re.split(r"(?<=[.!?؟])\s", text.strip(), maxsplit=1)[0].rstrip(".")


def standup_output(items: list[dict[str, str]], arabic: bool) -> dict[str, Any]:
    """One entry per token; a summary that names who is blocked and nothing counted."""
    tokens = sorted({item["token"] for item in items}, key=lambda t: int(t[1:]))
    entries = []
    for token in tokens:
        parts: dict[str, list[str]] = {"done": [], "doing": [], "blocked": []}
        for item in items:
            if item["token"] == token:
                for name, lines in split_update(item["text"]).items():
                    parts[name] += lines
        entries.append({"participant": token, **parts})
    blocked = [str(e["participant"]) for e in entries if e["blocked"]]
    if arabic:
        summary = "قدّم " + "، ".join(tokens) + " تحديثاتهم في هذه النافذة."
        summary += (" المعطلون: " + "، ".join(blocked) + ".") if blocked else ""
    else:
        summary = ", ".join(tokens) + " reported in this window."
        summary += (" Blocked: " + ", ".join(blocked) + ".") if blocked else ""
    return {
        "summary": summary,
        "participants_mentioned": tokens,
        "empty_reason": None,
        "rationale": "One entry per token; the cued parts of each update; nothing counted.",
        "standup": entries,
    }


def digest_output(items: list[dict[str, str]], arabic: bool) -> dict[str, Any]:
    """One group per kind in the data; the items' own sentences; no number that is a count."""
    kinds: list[str] = []
    for item in items:
        if item["kind"] and item["kind"] not in kinds:
            kinds.append(item["kind"])
    groups = [
        {
            "kind": kind,
            "changes": [first_sentence(i["text"]) for i in items if i["kind"] == kind],
        }
        for kind in kinds
    ]
    first = first_sentence(items[0]["text"]) if items else ""
    if arabic:
        summary = "تغييرات في " + "، ".join(kinds) + f". أبرزها: {first}."
    else:
        summary = "Changes across " + ", ".join(kinds) + f". Most notable: {first}."
    return {
        "summary": summary,
        "participants_mentioned": [],
        "empty_reason": None,
        "rationale": "Grouped by the kind each item carries; the product states the counts.",
        "digest": groups,
    }


def answer_window(body: dict[str, Any], mode: str, thread: str, forced: bool) -> dict[str, Any]:
    """Build a provider-shaped standup or digest from the fenced thread, in the items' script."""
    items = items_of(thread)
    texts = " ".join(item["text"] for item in items)
    arabic = forced or len(ARABIC_LETTER.findall(texts)) > len(LATIN_LETTER.findall(texts))
    if not items:
        output: dict[str, Any] = {
            "summary": "",
            "participants_mentioned": [],
            "empty_reason": "nothing_to_summarize",
            "rationale": "The window holds nothing.",
        }
    elif mode == "standup":
        output = standup_output(items, arabic)
    else:
        output = digest_output(items, arabic)
    return envelope(body, json.dumps(output, ensure_ascii=False))
