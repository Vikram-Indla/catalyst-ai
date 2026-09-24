"""The authored stand-in for interpret-query over a list declaration: only declared parameters.

A rule-based reading that uses only what the prompt's declaration lists: a declared enum value (or
its Arabic word) becomes that parameter, a sorting phrase becomes a declared sort, an ISO date after
"after" or "before" becomes the field's From or To when the list declares it, in Latin digits
whatever the sentence wrote. A field the declaration does not hold ("by budget"), or a date with no
range declared, is left unresolved word for word. It never picks a neighbour.
"""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

MARKER = "The list's declaration"
FENCE = re.compile(r"<<<sentence>>>\n(?P<body>.*?)\n<<<end sentence>>>", re.S)
PARAM = re.compile(r"^- (?P<param>[a-zA-Z0-9]+) \((?P<type>\w+)\)(?:: (?P<values>.+))?$", re.M)
SORTS = re.compile(r"^Sorts: (?P<sorts>[^(]+)\(", re.M)
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
ARABIC_STATES = {
    "النشطة": "active",
    "المخطط لها": "planned",
    "المغلقة": "closed",
    "المعلقة": "pending",
    "المعتمدة": "approved",
    "المرفوضة": "rejected",
    "المسودة": "draft",
}
NEWEST = re.compile(r"\bnewest\b|\blatest\b|الأحدث")
BY_NAME = re.compile(r"\bby name\b|حسب الاسم")
DATED = re.compile(r"(?P<word>\bafter\b|\bbefore\b|بعد|قبل)\s+(?P<date>\d{4}-\d{2}-\d{2})")
UNKNOWN_FIELD = re.compile(
    r"(?:\bby (?P<en>budget|owner|cost)\b|حسب (?P<ar>الميزانية|المالك|التكلفة))"
)


def is_listing(turn: str) -> bool:
    """Return whether the prompt carries a list declaration rather than a grammar."""
    return MARKER in turn


def _declaration(turn: str) -> tuple[dict[str, list[str]], list[str], list[str]]:
    enums = {
        m.group("param"): [v.strip() for v in m.group("values").split("|")]
        for m in PARAM.finditer(turn)
        if m.group("type") == "enum" and m.group("values")
    }
    dates = [
        m.group("param") for m in PARAM.finditer(turn) if m.group("type") in ("date", "datetime")
    ]
    found = SORTS.search(turn)
    sorts = [s.strip() for s in found.group("sorts").split(",")] if found else []
    return enums, dates, sorts


def _enum_values(sentence: str, enums: dict[str, list[str]]) -> dict[str, str]:
    lowered = sentence.lower()
    chosen: dict[str, str] = {}
    for param, values in enums.items():
        for value in values:
            arabic = [word for word, meaning in ARABIC_STATES.items() if meaning == value]
            if re.search(rf"\b{re.escape(value)}\b", lowered) or any(w in sentence for w in arabic):
                chosen[param] = value
    return chosen


def _sort(sentence: str, sorts: list[str]) -> str | None:
    if NEWEST.search(sentence):
        return next((s for s in sorts if s.startswith("-")), None)
    if BY_NAME.search(sentence):
        return "name" if "name" in sorts else None
    return None


def read(sentence: str, turn: str) -> tuple[dict[str, str], str | None, list[str]]:
    """Return the parameters, the sort and the unresolved terms for a sentence."""
    enums, dates, sorts = _declaration(turn)
    latin = sentence.translate(DIGITS)
    parameters = _enum_values(latin, enums)
    unresolved = []
    for match in DATED.finditer(latin):
        after = match.group("word") in ("after", "بعد")
        suffix = "From" if after else "To"
        param = next((d for d in dates if d.endswith(suffix)), None)
        if param is None:
            unresolved.append(match.group(0))
        else:
            parameters[param] = match.group("date")
    unknown = UNKNOWN_FIELD.search(latin)
    if unknown:
        unresolved.append(unknown.group("en") or unknown.group("ar"))
    return parameters, _sort(latin, sorts), unresolved


def answer_listing(body: dict[str, Any]) -> dict[str, Any]:
    """Build the interpret-query answer over a list declaration."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fenced = FENCE.search(turn)
    sentence = fenced.group("body") if fenced else ""
    parameters, sort, unresolved = read(sentence, turn)
    arabic = bool(re.search(r"[؀-ۿ]", sentence))
    shown = ", ".join(f"{k}={v}" for k, v in parameters.items()) or "-"
    explanation = f"تصفية القائمة: {shown}" if arabic else f"List filter: {shown}"
    output = {
        "query": "",
        "parameters": parameters,
        "sort": sort,
        "explanation": explanation,
        "unresolved": unresolved,
        "rationale": "Only the list's declared parameters and sorts; the rest left unresolved.",
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))
