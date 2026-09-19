"""The authored stand-in: a rule-based, provider-shaped answer for fixtures while no key exists."""

import json
import re
from typing import Any

CHARS_PER_TOKEN = 4
FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
OPERATION = re.compile(r"^Operation: (?P<mode>[a-z_]+)$", re.M)
CUES = (
    "ignore previous",
    "ignore the description",
    "you are now",
    "act as",
    "reveal",
    "instruction",
    "bypass",
    "tenant",
    "hacked",
    "[system]",
    "<<",
    ">>",
)
REFUSAL_CUES = (
    "ignore previous instructions",
    "reveal your system prompt",
    "as an image",
)
TYPOS = (
    ("dont", "don't"),
    ("shoud", "should"),
    ("teh", "the"),
    ("stays", "stay"),
    (" i ", " I "),
    ("veut", "veux"),
)
EXPAND_SUFFIX = (
    " In practice this means the behaviour above applies to every affected screen, the result"
    " is visible immediately, and the existing data is left untouched."
)
CRITERIA_TEMPLATE = (
    "- Given the item {title!r}, when the described behaviour runs, then the outcome matches"
    " the description.\n- Given the same starting state, when the action runs twice, then the"
    " second run changes nothing."
)
EDGE_TEMPLATE = (
    "\n- Given an invalid input, when the action runs, then an error is reported and nothing"
    " changes.\n- Given a timeout during the action, when it is retried, then no duplicate result"
    " appears."
)
USER_STORY_TEMPLATE = "As a user, I want {goal}, so that {benefit}."
SHORTEN_SHARE = 0.45


def _segments(body: dict[str, Any]) -> tuple[dict[str, str], str]:
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    match = OPERATION.search(turn)
    return fields, match.group("mode") if match else "clarify"


def _clean_sentences(text: str) -> str:
    kept = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lowered = sentence.lower()
        if not any(cue in lowered for cue in CUES):
            kept.append(sentence)
    return " ".join(kept).strip()


def _clarify(text: str) -> str:
    fixed = _clean_sentences(text)
    for wrong, right in TYPOS:
        fixed = fixed.replace(wrong, right)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", fixed) if s.strip()]
    sentences = [s[0].upper() + s[1:] for s in sentences]
    result = " ".join(sentences)
    return result if not result or result.endswith((".", "!", "?", "|")) else result + "."


def _shorten(text: str) -> str:
    words = _clean_sentences(text).split()
    keep = max(4, int(len(words) * SHORTEN_SHARE))
    return " ".join(words[:keep]).rstrip(",;") + "."


def answer(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped response for the request body, deterministic and well-behaved."""
    if CHILD_LEVEL.search("".join(p.get("text", "") for p in body["contents"][0]["parts"])):
        return answer_children(body)
    fields, mode = _segments(body)
    description = fields.get("description", "")
    title = fields.get("title", "")
    criteria = fields.get("acceptance_criteria", "")
    absent = description in ("", "(none)")
    lowered = (description + " " + fields.get("focus_hint", "")).lower()
    refused = any(cue in lowered for cue in REFUSAL_CUES)
    output: dict[str, Any] = {
        "description": description if not absent else "",
        "acceptance_criteria": None,
        "changed": False,
        "rationale": "Returned unchanged.",
    }
    if refused or absent:
        output["rationale"] = (
            "The text asks for something outside editing; returned unchanged."
            if refused
            else "Nothing to edit."
        )
    elif mode == "clarify":
        output["description"] = _clarify(description)
    elif mode == "expand":
        output["description"] = _clarify(description) + EXPAND_SUFFIX
    elif mode == "shorten":
        output["description"] = _shorten(description)
    elif mode == "user_story":
        benefit = _clean_sentences(description).rstrip(".").lower()
        output["description"] = USER_STORY_TEMPLATE.format(
            goal=title.lower(), benefit=benefit or "the work is done"
        )
    elif mode == "acceptance_criteria":
        output["acceptance_criteria"] = CRITERIA_TEMPLATE.format(title=title)
    elif mode == "edge_cases":
        output["acceptance_criteria"] = (criteria if criteria != "(none)" else "") + EDGE_TEMPLATE
    if not refused and not absent:
        output["changed"] = (
            output["description"] != description or output["acceptance_criteria"] is not None
        )
        output["rationale"] = (
            f"Applied the {mode} operation: tightened phrasing and kept every fact."
            if output["changed"]
            else "Already clear; only checked grammar."
        )
    return _envelope(body, json.dumps(output, ensure_ascii=False))


def _envelope(body: dict[str, Any], text: str) -> dict[str, Any]:
    prompt_chars = sum(len(p.get("text", "")) for c in body["contents"] for p in c["parts"])
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {
            "promptTokenCount": prompt_chars // CHARS_PER_TOKEN,
            "candidatesTokenCount": len(text) // CHARS_PER_TOKEN,
        },
        "modelVersion": "authored-stand-in",
    }


CHILD_LEVEL = re.compile(
    r"^Child level: <<<child_level>>>\n(?P<level>.+?)\n<<<end child_level>>>", re.M | re.S
)
MAX_ITEMS_LINE = re.compile(r"^At most: (?P<n>\d+) candidates$", re.M)
STORY_LIKE = ("story", "feature")
CRITERIA = (
    "Given the parent's context, when the work is delivered, then the outcome in the title holds.",
    "Given an error during the work, when it is retried, then no duplicate side effect appears.",
)


def _clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+|\n+|,\s+(?:and|then|also)\s+", _clean_sentences(text))
    return [p.strip(" .;,") for p in parts if len(p.strip()) > 12]


def _child_candidates(fields: dict[str, str], level: str, limit: int) -> list[dict[str, Any]]:
    siblings = [
        s.strip("- ")
        for s in fields.get("siblings", "").split("\n")
        if s.strip("- ") and s.strip("- ") != "(none)"
    ]
    clauses = _clauses(fields.get("parent_description", "")) or _clauses(
        fields.get("source_texts", "")
    )
    out: list[dict[str, Any]] = []
    for clause in clauses[: limit + len(siblings)]:
        title = clause[0].upper() + clause[1:]
        duplicate = next((s for s in siblings if similarity_stub(title, s)), None)
        criteria = list(CRITERIA) if level.lower() in STORY_LIKE else []
        out.append(
            {
                "type": level,
                "title": title,
                "description": f"{title}, as part of the parent.",
                "acceptance_criteria": criteria,
                "duplicate_of": duplicate,
            }
        )
    return out


def similarity_stub(left: str, right: str) -> bool:
    """Whether two titles share most of their words; the stand-in's notion of a repeat."""
    a = {w for w in re.findall(r"\w+", left.lower()) if len(w) > 2}
    b = {w for w in re.findall(r"\w+", right.lower()) if len(w) > 2}
    return bool(a) and bool(b) and len(a & b) / min(len(a), len(b)) >= 0.6


def answer_children(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped response for a generate-children request body."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    level_match = CHILD_LEVEL.search(turn)
    level = level_match.group("level").strip() if level_match else "story"
    limit_match = MAX_ITEMS_LINE.search(turn)
    limit = int(limit_match.group("n")) if limit_match else 7
    description = fields.get("parent_description", "")
    lowered = (description + " " + fields.get("focus_hint", "")).lower()
    output: dict[str, Any] = {
        "candidates": [],
        "empty_reason": None,
        "rationale": "Proposed children from the parent's text.",
    }
    if (
        any(cue in lowered for cue in REFUSAL_CUES)
        or description in ("", "(none)")
        or len(description) < 20
    ):
        output["empty_reason"] = "parent_too_vague"
        output["rationale"] = "The parent gives too little to break down."
    else:
        output["candidates"] = _child_candidates(fields, level, limit)
        if not output["candidates"]:
            output["empty_reason"] = "parent_too_vague"
        elif all(c["duplicate_of"] for c in output["candidates"]):
            output["empty_reason"] = "siblings_cover_it"
    return _envelope(body, json.dumps(output, ensure_ascii=False))
