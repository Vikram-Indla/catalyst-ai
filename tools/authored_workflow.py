"""The authored stand-in for workflow proposals: sentence patterns in, a scheme out, disclosed."""

import json
import re
from typing import Any

from tools.authored_envelope import envelope
from tools.workflow_terms import GUARD_PHRASES, PROCESSES

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
CATEGORIES_LINE = re.compile(r"^Allowed categories: (?P<c>.+)$", re.M)
GUARDS_LINE = re.compile(r"^Guard vocabulary: (?P<g>.+)$", re.M)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
KEY_OF_ARABIC = {stage[2]: stage[0] for family in PROCESSES.values() for stage in family[0]}
GUARD_OF_PHRASE = {phrase: key for key, phrases in GUARD_PHRASES.items() for phrase in phrases}
PATTERNS = (
    ("start", re.compile(r"^(?:It starts as|يبدأ كـ) (?P<a>.+)$")),
    ("end", re.compile(r"^(?:It ends as|ينتهي كـ) (?P<a>.+)$")),
    ("waiting", re.compile(r"^(?P<a>.+?) (?:is a waiting state|حالة انتظار)$")),
    ("cancel", re.compile(r"^(?:Any item can be cancelled as|يمكن إلغاء أي عنصر كـ) (?P<b>.+)$")),
    (
        "forward",
        re.compile(r"^(?:From (?P<a>.+?) it moves to|من (?P<a2>.+?) ينتقل إلى) (?P<b>.+)$"),
    ),
    (
        "backward",
        re.compile(
            r"^(?:It can go back from|يمكن إرجاعه من) (?P<a>.+?) (?:to|إلى) "
            r"(?P<b>.+?)(?: with a reason| مع سبب)$"
        ),
    ),
    (
        "reject",
        re.compile(
            r"^(?:It can be rejected from|يمكن رفضه من) (?P<a>.+?) (?:back to|إلى) "
            r"(?P<b>.+?)(?: with a reason| مع سبب)$"
        ),
    ),
    (
        "reopen",
        re.compile(
            r"^(?:It can be reopened from|يمكن إعادة فتحه من) (?P<a>.+?) (?:to|إلى) "
            r"(?P<b>.+?)(?: with a reason| مع سبب)$"
        ),
    ),
    (
        "defer",
        re.compile(r"^(?:It can be deferred from|يمكن تأجيله من) (?P<a>.+?) (?:to|إلى) (?P<b>.+)$"),
    ),
    (
        "exception",
        re.compile(
            r"^(?:In an exception it can jump from|في حالة استثنائية يمكن نقله من) "
            r"(?P<a>.+?) (?:to|إلى) (?P<b>.+)$"
        ),
    ),
)
REASON_KINDS = frozenset({"backward", "reject", "reopen"})


def key_of(label: str) -> str:
    """Return a snake-case key from an English label, or the table's key for an Arabic one."""
    if label in KEY_OF_ARABIC:
        return KEY_OF_ARABIC[label]
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "status"


def split_guard(target: str) -> tuple[str, str | None]:
    """Cut a guard phrase off the end of a target label; return the label and the guard key."""
    for phrase, key in GUARD_OF_PHRASE.items():
        if target.endswith(" " + phrase):
            return target[: -len(phrase) - 1], key
    return target, None


class SchemeBuilder:
    """Collect the facts of the sentences, then lay them out as statuses and transitions."""

    def __init__(self, categories: list[str], vocabulary: list[str], arabic: bool) -> None:
        """Start empty; the categories and vocabulary come from the developer lines."""
        self.categories = categories
        self.vocabulary = vocabulary
        self.arabic = arabic
        self.labels: dict[str, str] = {}
        self.initial: str | None = None
        self.terminals: list[str] = []
        self.waiting: set[str] = set()
        self.moves: list[tuple[str | None, str, str, str | None]] = []

    def _note(self, label: str) -> str:
        key = key_of(label)
        self.labels.setdefault(key, label)
        return key

    def take(self, kind: str, match: re.Match[str]) -> None:
        """Record one sentence's fact."""
        groups = match.groupdict()
        source = groups.get("a") or groups.get("a2")
        if kind == "start":
            self.initial = self._note(str(source))
        elif kind == "end":
            self.terminals.append(self._note(str(source)))
        elif kind == "waiting":
            self.waiting.add(self._note(str(source)))
        elif kind == "cancel":
            self.moves.append((None, self._note(groups["b"]), "cancel", None))
        else:
            target, guard = split_guard(groups["b"])
            self.moves.append((self._note(str(source)), self._note(target), kind, guard))

    def _category(self, key: str) -> str:
        if key in self.terminals:
            return "done"
        waiting = key == self.initial or key in self.waiting
        return "todo" if waiting or "in_progress" not in self.categories else "in_progress"

    def statuses(self) -> list[dict[str, Any]]:
        """Every status named, in order of first mention."""
        return [
            {
                "key": key,
                "name": label,
                "category": self._category(key),
                "initial": key == self.initial,
                "terminal": key in self.terminals,
                "order": index,
            }
            for index, (key, label) in enumerate(self.labels.items())
        ]

    def _rationale(self, source: str | None, target: str) -> str:
        a = self.labels.get(source or "", "any status")
        b = self.labels[target]
        if self.arabic:
            return f"الوصف يذكر الانتقال من {a} إلى {b}."
        return f"The description says it moves from {a} to {b}."

    def transitions(self) -> list[dict[str, Any]]:
        """Every move: its guard when the vocabulary knows it, a reason where the kind needs one."""
        return [
            {
                "from_key": source,
                "to_key": target,
                "kind": kind,
                "guards": [guard] if guard in self.vocabulary else [],
                "reason_code": f"{kind}_to_{target}" if kind in REASON_KINDS else None,
                "rationale": self._rationale(source, target),
            }
            for source, target, kind, guard in self.moves
        ]


def build(
    description: str, categories: list[str], vocabulary: list[str], arabic: bool
) -> dict[str, Any]:
    """Read the description sentence by sentence; unknown sentences are ignored as text."""
    builder = SchemeBuilder(categories, vocabulary, arabic)
    for sentence in SENTENCE.split(description.strip()):
        bare = sentence.strip().rstrip(".!?")
        for kind, pattern in PATTERNS:
            match = pattern.match(bare)
            if match:
                builder.take(kind, match)
                break
    if builder.initial is None:
        return {
            "statuses": [],
            "transitions": [],
            "empty_reason": "description_too_vague",
            "rationale": "The description names no starting state.",
        }
    return {
        "statuses": builder.statuses(),
        "transitions": builder.transitions(),
        "empty_reason": None,
        "rationale": "One status per state named, one transition per move described.",
    }


def answer_workflow(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped proposal from the fenced description and the developer lines."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    categories_match = CATEGORIES_LINE.search(turn)
    categories = (
        [c.strip() for c in categories_match.group("c").split(",")] if categories_match else []
    )
    guards_match = GUARDS_LINE.search(turn)
    vocabulary = [g.strip() for g in guards_match.group("g").split(",")] if guards_match else []
    arabic = "Language of labels and rationales: ar" in turn
    output = build(fields.get("description", ""), categories, vocabulary, arabic)
    return envelope(body, json.dumps(output, ensure_ascii=False))
