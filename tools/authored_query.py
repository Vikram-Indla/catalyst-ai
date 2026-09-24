"""The authored stand-in for interpret-query: phrases matched in order, the rest left unresolved.

A rule-based reading of English and Arabic phrases into clauses of the list grammar, so the
fixtures exercise the pipeline, the grammar check and the graders without a key. It is not the
model's judgement: it knows only the phrases below, reads "today" from the moment the prompt
gives (already in the organisation's zone), drops an injected instruction with everything after
it, and returns what it could not place, word for word, trimmed of filler at its edges.
"""

import json
import re
from typing import Any

from tools.authored_envelope import envelope
from tools.authored_listing import answer_listing, is_listing

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
NOW = re.compile(r"^Now: (?P<date>\d{4}-\d{2}-\d{2})", re.M)
INJECTION = re.compile(
    r"(ignore (all )?previous instructions|reveal your system prompt|تجاهل التعليمات).*$", re.S
)
DONE = 'status = "Done"'
NOT_DONE = 'status != "Done"'
PHRASES: tuple[tuple[str, str], ...] = (
    (r"\breported by me\b", "reporter = currentUser()"),
    (r"\bassigned to me\b|\bmy\b", "assignee = currentUser()"),
    (r"\bunassigned\b|غير المسندة", "assignee IS EMPTY"),
    (r"\bopen sprints\b", "sprint IN (openSprints())"),
    (r"\bwithout a sprint\b", "sprint IS EMPTY"),
    (r"\bwhose status changed\b", "status CHANGED"),
    (r"\bwere in review\b", 'status WAS "In Review"'),
    (r"\bin review\b|قيد المراجعة", 'status = "In Review"'),
    (r"\bin progress\b", 'status = "In Progress"'),
    (r"\bnot done\b|\bexcept done\b|ما عدا المنجز|المفتوحة|\bopen\b", NOT_DONE),
    (r"\bdone\b|المنجزة", DONE),
    (r"\bnot bugs\b", 'issuetype != "Bug"'),
    (r"أخطائي", 'assignee = currentUser() AND issuetype = "Bug"'),
    (r"\bbugs?\b|الأخطاء|أخطاء", 'issuetype = "Bug"'),
    (r"\bstor(y|ies)\b|القصص", 'issuetype = "Story"'),
    (r"\btasks?\b|المهام", 'issuetype = "Task"'),
    (r"\bepics?\b|الملاحم", 'issuetype = "Epic"'),
    (r"\bhighest or high priority\b", 'priority IN ("High", "Highest")'),
    (r"\bhigh priority\b|الأولوية العالية", 'priority = "High"'),
    (
        r"\bcreated in the last (?P<n>\d+) days\b|أنشئت في آخر (?P<ar>\d+) أيام",
        'created >= "-{n}d"',
    ),
    (r"\bupdated this week\b", "updated >= startOfWeek()"),
    (r"\bdue this month\b", "duedate >= startOfMonth()"),
    (r"\bdue today\b|المستحقة اليوم", 'duedate = "{today}"'),
    (r"\boverdue\b", f'duedate < "{{today}}" AND {NOT_DONE}'),
    (r"\blabelled (?P<label>[a-z0-9_-]+)\b", 'labels = "{label}"'),
)
ORDERINGS: tuple[tuple[str, str], ...] = (
    (r"\bnewest\b|أحدث", "created DESC"),
    (r"\boldest\b", "created ASC"),
    (r"\bsorted by priority\b", "priority DESC"),
)
FILLER = frozenset(
    [
        "items",
        "item",
        "everything",
        "that",
        "are",
        "the",
        "in",
        "a",
        "an",
        "and",
        "of",
        "by",
        "with",
        "to",
        "first",
        "whose",
        "is",
        "all",
        "every",
        "return",
        "where",
        "العناصر",
        "كل",
        "شيء",
        "التي",
        "ذات",
        "في",
        "و",
        "أولا",
    ]
)


def _sentence_and_today(body: dict[str, Any]) -> tuple[str, str]:
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fields = {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}
    today = NOW.search(turn)
    return fields.get("sentence", ""), today.group("date") if today else ""


def _clause(template: str, match: re.Match[str], today: str) -> str:
    groups = {key: value for key, value in match.groupdict().items() if value}
    count = groups.get("n") or groups.get("ar") or ""
    return template.format(n=count, today=today, label=groups.get("label", ""))


def _leftover(text: str) -> list[str]:
    words = [w.strip(",.;:!?،") for w in text.split()]
    words = [w for w in words if w]
    while words and words[0].lower() in FILLER:
        words.pop(0)
    while words and words[-1].lower() in FILLER:
        words.pop()
    return [" ".join(words)] if words else []


def interpret(sentence: str, today: str) -> tuple[str, list[str]]:
    """Return the query the phrases make and what was left over."""
    working = INJECTION.sub(" ", sentence.lower())
    clauses: list[str] = []
    for pattern, template in PHRASES:
        match = re.search(pattern, working)
        if match:
            clauses.append(_clause(template, match, today))
            working = working[: match.start()] + " " + working[match.end() :]
    order = []
    for pattern, key in ORDERINGS:
        match = re.search(pattern, working)
        if match:
            order.append(key)
            working = working[: match.start()] + " " + working[match.end() :]
    query = " AND ".join(dict.fromkeys(clauses))
    if order:
        query = f"{query} ORDER BY {', '.join(order)}".strip()
    return query, _leftover(working)


def answer_query(body: dict[str, Any]) -> dict[str, Any]:
    """Build the interpret-query answer for one prompt: a query, or a list's parameters."""
    if is_listing("".join(part.get("text", "") for part in body["contents"][0]["parts"])):
        return answer_listing(body)
    sentence, today = _sentence_and_today(body)
    query, unresolved = interpret(sentence, today)
    arabic = bool(re.search(r"[؀-ۿ]", sentence))
    if query:
        explanation = f"تصفية: {query}" if arabic else f"Filter: {query}"
    else:
        explanation = "لا شيء في الجملة يطابق مرشحا" if arabic else "Nothing in it maps to a filter"
    output = {
        "query": query,
        "explanation": explanation,
        "unresolved": unresolved,
        "rationale": "Phrases matched against the grammar; the rest left unresolved.",
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))
