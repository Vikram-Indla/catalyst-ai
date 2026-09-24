"""The authored stand-in for improve-story's comment modes: a polished comment, a suggested reply.

Deterministic and well-behaved, like every stand-in: a polish fixes spelling and the sentence's
shape and touches no mention, link or code span; a reply addresses the comment's author by token,
in the comment's script, and names nothing the inputs do not. A comment that carries an injection
cue comes back unchanged.
"""

import json
import re
from typing import Any

from catalyst_ai.platform.language import dominant_script
from tools.authored_envelope import envelope

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
OPERATION = re.compile(r"^Operation: (?P<mode>[a-z_]+)$", re.M)
AUTHOR = re.compile(r"^Comment by: (?P<author>p[0-9]{1,4})$", re.M)
PROTECTED = re.compile(r"(@p[0-9]{1,4}\b|https?://[^\s)>\]]+|`[^`\n]+`)")
COMMENT_MODES = ("polish_comment", "reply")
INJECTION = ("ignore previous instructions", "reveal your system prompt", "you are now")
SPELLING = (
    ("dont", "don't"),
    ("cant", "can't"),
    ("teh", "the"),
    ("recieve", "receive"),
    ("becuase", "because"),
    ("pls", "please"),
)
ARABIC = "ARABIC"


def is_comment_mode(body: dict[str, Any]) -> bool:
    """Return whether the request asks for one of the comment modes."""
    match = OPERATION.search(_turn(body))
    return match is not None and match.group("mode") in COMMENT_MODES


def _turn(body: dict[str, Any]) -> str:
    return "".join(part.get("text", "") for part in body["contents"][0]["parts"])


def _fix(piece: str) -> str:
    for wrong, right in SPELLING:
        piece = re.sub(rf"\b{wrong}\b", right, piece)
    return re.sub(r"\bi\b", "I", piece)


def polish(text: str) -> str:
    """Fix spelling and the sentence's shape outside every mention, link and code span."""
    pieces = PROTECTED.split(text)
    fixed = "".join(p if PROTECTED.fullmatch(p) else _fix(p) for p in pieces).strip()
    if fixed and fixed[0].isalpha():
        fixed = fixed[0].upper() + fixed[1:]
    return fixed if fixed.endswith((".", "!", "?", "`", "؟")) else fixed + "."


REPLIES = {
    (True, True): "شكرًا @{author}. وصف «{title}» لا يجيب عن هذا بعد؛ هل يمكنك إضافة التفاصيل؟",
    (True, False): "شكرًا @{author}، اطلعنا على ملاحظتك بخصوص «{title}» وسنتابعها هنا.",
    (False, True): (
        "Thanks @{author}. The description of '{title}' does not answer this yet; "
        "could you add the detail you need?"
    ),
    (False, False): "Thanks @{author}, noted on '{title}'; we will follow up here.",
}


def reply(text: str, author: str, title: str) -> str:
    """Suggest a reply to the author, in the comment's script, from the item's title alone."""
    arabic = dominant_script(text) == ARABIC
    asks = text.rstrip().endswith(("?", "؟"))
    return REPLIES[(arabic, asks)].format(author=author, title=title)


def answer_comment(body: dict[str, Any]) -> dict[str, Any]:
    """Build the provider-shaped answer for a comment mode."""
    turn = _turn(body)
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    mode_match = OPERATION.search(turn)
    author_match = AUTHOR.search(turn)
    mode = mode_match.group("mode") if mode_match else "polish_comment"
    author = author_match.group("author") if author_match else "p1"
    comment = fields.get("comment", "")
    refused = any(cue in comment.lower() for cue in INJECTION)
    if refused:
        text, rationale = comment, "The comment asks for something outside editing; unchanged."
    elif mode == "reply":
        text, rationale = reply(comment, author, fields.get("title", "")), "Suggested a reply."
    else:
        text, rationale = polish(comment), "Fixed spelling and phrasing; kept every mention."
    output = {
        "description": text,
        "acceptance_criteria": None,
        "changed": text != comment,
        "rationale": rationale,
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))
