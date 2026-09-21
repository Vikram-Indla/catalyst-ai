"""The authored stand-in for summaries and translations: rule-based, provider-shaped, disclosed."""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

THREAD_LINE = re.compile(r"^\[(?P<id>[^\]]+)\] (?P<token>p\d+) @ (?P<at>\S+): (?P<text>.*)$")
STATUS_LINE = re.compile(r"^(?P<token>p\d+) moved it from (?P<old>.+?) to (?P<new>.+?) at ")
TARGET_LINE = re.compile(r"^Target length: about (?P<n>\d+) words", re.M)
TARGET_LANGUAGE_LINE = re.compile(r"^Target language: (?P<lang>\S+)", re.M)
MODE_LINE = re.compile(r"^Mode: (?P<mode>\w+)", re.M)
FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
DECISION = ("decid", "agreed", "قرار", "قررنا", "متفق")
BLOCKER = ("block", "معطل")
QUESTION = ("?", "؟")
ACTION = ("action item", "will take", "سأتولى")
LATIN_TO_ARABIC = {
    "a": "ا",
    "b": "ب",
    "c": "ك",
    "d": "د",
    "e": "ي",
    "f": "ف",
    "g": "غ",
    "h": "ه",
    "i": "ي",
    "j": "ج",
    "k": "ك",
    "l": "ل",
    "m": "م",
    "n": "ن",
    "o": "و",
    "p": "ب",
    "q": "ق",
    "r": "ر",
    "s": "س",
    "t": "ت",
    "u": "و",
    "v": "ف",
    "w": "و",
    "x": "كس",
    "y": "ي",
    "z": "ز",
}
ARABIC_TO_LATIN = {
    "ا": "a",
    "أ": "a",
    "إ": "i",
    "آ": "a",
    "ب": "b",
    "ت": "t",
    "ث": "th",
    "ج": "j",
    "ح": "h",
    "خ": "kh",
    "د": "d",
    "ذ": "dh",
    "ر": "r",
    "ز": "z",
    "س": "s",
    "ش": "sh",
    "ص": "s",
    "ض": "d",
    "ط": "t",
    "ظ": "z",
    "ع": "a",
    "غ": "gh",
    "ف": "f",
    "ق": "q",
    "ك": "k",
    "ل": "l",
    "م": "m",
    "ن": "n",
    "ه": "h",
    "و": "w",
    "ي": "y",
    "ى": "a",
    "ة": "a",
    "ء": "",
    "ئ": "i",
    "ؤ": "u",
    "ً": "",
    "ٌ": "",
    "ٍ": "",
    "َ": "",
    "ُ": "",
    "ِ": "",
    "ّ": "",
    "ْ": "",
    "،": ",",
    "؟": "?",
}
KEPT = re.compile(
    r"```.*?```|`[^`\n]+`|https?://\S+|\{\{[^}]*\}\}|\$\{[^}]*\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%[sd]"
    r"|\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b|\b(?:Staging|CSV|PDF|API|DNS)\b",
    re.S,
)
ARABIC_WORD = re.compile(r"[؀-ۿ]+")
LATIN_WORD = re.compile(r"[A-Za-z]+")


def _thread(body: str) -> list[dict[str, str]]:
    items = []
    for line in body.splitlines():
        match = THREAD_LINE.match(line)
        if match:
            items.append(match.groupdict())
    return items


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?؟])\s", text.strip(), maxsplit=1)[0]


def _bullets(items: list[dict[str, str]]) -> list[str]:
    bullets = []
    for item in items:
        lowered = item["text"].lower()
        sentence = _first_sentence(item["text"])
        if any(cue in lowered for cue in DECISION):
            bullets.append(f"- {item['token']} — decision: {sentence}")
        elif any(cue in lowered for cue in BLOCKER):
            bullets.append(f"- {item['token']} — blocker: {sentence}")
        elif any(cue in item["text"] for cue in QUESTION):
            bullets.append(f"- {item['token']} — open question: {sentence}")
        elif any(cue in lowered for cue in ACTION):
            bullets.append(f"- {item['token']} — action item: {sentence}")
    return bullets


def answer_summary(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped summary: a lead paragraph, bullets by cue, status changes, a cap."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    items = _thread(fields.get("thread", ""))
    target = TARGET_LINE.search(turn)
    limit = int(target.group("n")) if target else 150
    if not items:
        output: dict[str, Any] = {
            "summary": "",
            "participants_mentioned": [],
            "empty_reason": "nothing_to_summarize",
            "rationale": "The thread is empty.",
        }
        return envelope(body, json.dumps(output, ensure_ascii=False))
    tokens = sorted({item["token"] for item in items}, key=lambda t: int(t[1:]))
    latest = items[-1]
    lead = (
        f"{len(items)} comment(s) from {', '.join(tokens)}; the latest, by {latest['token']}, "
        f"says: {_first_sentence(latest['text'])}"
    )
    bullets = _bullets(items)
    for line in fields.get("status_changes", "").splitlines():
        match = STATUS_LINE.match(line)
        if match:
            bullets.append(
                f"- {match.group('token')} moved it from {match.group('old')}"
                f" to {match.group('new')}"
            )
    words = (lead + "\n\n" + "\n".join(bullets)).split(" ")
    summary = " ".join(words[:limit])
    output = {
        "summary": summary,
        "participants_mentioned": [t for t in tokens if t in summary],
        "empty_reason": None,
        "rationale": "Kept the latest position, the cued bullets and the recorded moves.",
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))


def _to_arabic(text: str) -> str:
    return LATIN_WORD.sub(
        lambda m: "".join(LATIN_TO_ARABIC.get(c, c) for c in m.group(0).lower()), text
    )


def _to_latin(text: str) -> str:
    return ARABIC_WORD.sub(lambda m: "".join(ARABIC_TO_LATIN.get(c, c) for c in m.group(0)), text)


def _convert(text: str, target: str) -> str:
    pieces = []
    last = 0
    for match in KEPT.finditer(text):
        pieces.append(
            _to_arabic(text[last : match.start()])
            if target == "ar"
            else _to_latin(text[last : match.start()])
        )
        pieces.append(match.group(0))
        last = match.end()
    tail = text[last:]
    pieces.append(_to_arabic(tail) if target == "ar" else _to_latin(tail))
    return "".join(pieces)


def answer_translation(body: dict[str, Any]) -> dict[str, Any]:
    """Map scripts word by word, keeping code, links, keys and placeholders — no meaning."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    target_match = TARGET_LANGUAGE_LINE.search(turn)
    target = target_match.group("lang") if target_match else "en"
    text = fields.get("text", "")
    detected = "ar" if ARABIC_WORD.search(text) else "en"
    output = {
        "translated_text": _convert(text, target.split("-")[0]),
        "detected_language": detected,
        "rationale": "Mapped every word into the target script; kept code, links and keys.",
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))
