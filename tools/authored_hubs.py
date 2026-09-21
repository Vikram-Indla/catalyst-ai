"""The authored stand-ins for release notes, test generation and post-mortems: traced, disclosed."""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

FENCE = re.compile(r"<<<(?P<name>[a-z_]+)>>>\n(?P<body>.*?)\n<<<end (?P=name)>>>", re.S)
MODE_LINE = re.compile(r"^Mode: (?P<mode>\w+)", re.M)
AUDIENCE_LINE = re.compile(r"^Audience: (?P<a>\w+)", re.M)
MAX_CASES_LINE = re.compile(r"^At most this many cases: (?P<n>\d+)", re.M)
CHANGE_LINE = re.compile(
    r"^\[(?P<id>[^\]]+)\](?: (?P<key>[A-Z]+-\d+))? \((?P<kind>[a-z_]+), (?P<state>[a-z_]+)"
    r"(?: by (?P<token>p\d+))?\): (?P<title>.*)$"
)
CRITERION_LINE = re.compile(r"^\[(?P<id>[^\]]+)\] (?P<text>.*)$")
EVENT_LINE = re.compile(r"^\[(?P<id>[^\]]+)\](?: (?P<token>p\d+))? @ (?P<at>\S+): (?P<text>.*)$")
ARABIC_LETTER = re.compile(r"[؀-ۿ]")
LATIN_LETTER = re.compile(r"[A-Za-z]")
HIGHLIGHT_KINDS = ("story", "feature", "bug")
MAX_HIGHLIGHTS = 3
AREAS = ("happy", "negative", "boundary", "security", "performance", "integration")
PRIORITIES = ("critical", "high", "medium", "low")
FACTOR_CUES = ("deploy", "config", "cache key", "النشر", "مفتاح")
ACTION_CONFIDENCE = 0.7
INSTRUCTION_CUES = (
    "ignore the",
    "system:",
    "you are now",
    "<<<",
    "credential",
    "password",
    "blame",
)


def _instruction(text: str) -> bool:
    return any(cue in text.lower() for cue in INSTRUCTION_CUES)


FACTS_SHARE = 1.0


def _turn(body: dict[str, Any]) -> str:
    return "".join(part.get("text", "") for part in body["contents"][0]["parts"])


def _fields(turn: str) -> dict[str, str]:
    return {m.group("name"): m.group("body") for m in FENCE.finditer(turn)}


def _arabic(text: str) -> bool:
    return len(ARABIC_LETTER.findall(text)) > len(LATIN_LETTER.findall(text))


def _lines(body: str, pattern: re.Pattern[str]) -> list[dict[str, str]]:
    found = []
    for line in body.splitlines():
        match = pattern.match(line)
        if match:
            found.append({k: v or "" for k, v in match.groupdict().items()})
    return found


def _first_sentence(text: str) -> str:
    return re.split(r"(?<=[.!?؟])\s", text.strip(), maxsplit=1)[0].rstrip(".")


def _notes(changes: list[dict[str, str]], customer: bool) -> dict[str, Any]:
    done = [c for c in changes if c["state"] == "done"]
    if not done:
        return {"empty_reason": "nothing_to_report", "rationale": "Nothing is done yet."}
    sections: dict[str, list[dict[str, str]]] = {}
    for change in done:
        prefix = "" if customer or not change["key"] else f"{change['key']}: "
        who = "" if customer or not change["token"] else f" ({change['token']})"
        text = f"{prefix}{_first_sentence(change['title'])}{who}"
        sections.setdefault(change["kind"], []).append({"source_id": change["id"], "text": text})
    highlights = [
        {"source_id": c["id"], "text": _first_sentence(c["title"])}
        for c in done
        if c["kind"] in HIGHLIGHT_KINDS
    ][:MAX_HIGHLIGHTS]
    return {
        "sections": [{"kind": k, "entries": v} for k, v in sections.items()],
        "highlights": highlights,
        "summary": "",
        "attention": [],
        "empty_reason": None,
        "rationale": "One entry per done change, grouped by kind; nothing not done is noted.",
    }


def _overview(changes: list[dict[str, str]], release: str, arabic: bool) -> dict[str, Any]:
    done = [c for c in changes if c["state"] == "done"]
    open_ = [c for c in changes if c["state"] != "done"]
    name = release.splitlines()[0].removeprefix("name: ")
    comma = "، " if arabic else ", "
    landed = comma.join(_first_sentence(c["title"]) for c in done[:3])
    pending = comma.join(_first_sentence(c["title"]) for c in open_)
    if arabic:
        summary = f"الإصدار {name}: ما اكتمل حتى الآن: {landed or 'لا شيء بعد'}."
        summary += "\n\n- ما زال مفتوحاً قبل الموعد: " + (pending or "لا شيء")
    else:
        summary = f"Release {name}: landed so far — {landed or 'nothing yet'}."
        summary += "\n\n- Still open before the date: " + (pending or "nothing")
    attention = [
        {"source_id": c["id"], "text": f"{c['key'] or c['id']} is still {c['state']}"}
        for c in open_
    ]
    return {
        "sections": [],
        "highlights": [],
        "summary": summary,
        "attention": attention,
        "empty_reason": None,
        "rationale": "The release's state from its changes; open items need attention.",
    }


def answer_release(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped release note or overview from the fenced changes."""
    turn = _turn(body)
    fields = _fields(turn)
    changes = _lines(fields.get("changes", ""), CHANGE_LINE)
    mode = MODE_LINE.search(turn)
    audience = AUDIENCE_LINE.search(turn)
    arabic = _arabic(" ".join(c["title"] for c in changes))
    if mode and mode.group("mode") == "summary":
        output = _overview(changes, fields.get("release", ""), arabic)
    else:
        output = _notes(changes, audience is not None and audience.group("a") == "customer")
    return envelope(body, json.dumps(output, ensure_ascii=False))


def _cases(criteria: list[dict[str, str]], story: str, limit: int, arabic: bool) -> dict[str, Any]:
    if not criteria and "description:" not in story:
        return {"empty_reason": "nothing_to_test", "rationale": "The story states no behaviour."}
    testable = [c for c in criteria if not _instruction(c["text"])]
    cases: list[dict[str, Any]] = []
    for index, criterion in enumerate(testable):
        if index >= limit:
            cases[index % limit]["covers"].append(criterion["id"])
            continue
        text = _first_sentence(criterion["text"])
        cases.append(
            {
                "title": ("تحقق من " if arabic else "Verify ") + text.lower(),
                "given": "المستخدم مسجل الدخول" if arabic else "A signed-in member on the page",
                "when": text,
                "then": ("يتحقق " if arabic else "It holds: ") + text.lower(),
                "priority": PRIORITIES[index % len(PRIORITIES)],
                "area": AREAS[index % len(AREAS)],
                "covers": [criterion["id"]],
                "inferred": False,
            }
        )
    if len(cases) < limit:
        cases.append(
            {
                "title": "Verify the story's headline behaviour end to end",
                "given": "A signed-in member",
                "when": "The story's main flow runs",
                "then": "The outcome the story describes is observed",
                "priority": "high",
                "area": "integration",
                "covers": [],
                "inferred": True,
            }
        )
    return {
        "cases": cases,
        "gaps": [],
        "outline": [],
        "data_tables": [],
        "empty_reason": None,
        "rationale": "One case per criterion, areas blended, one inferred end-to-end case.",
    }


def _artefacts(existing: list[dict[str, str]]) -> dict[str, Any]:
    ids = [c["id"] for c in existing]
    outline = [
        {"heading": heading, "lines": [line], "covers": ids}
        for heading, line in (
            ("Scope", "The cases listed, run manually on the staging environment"),
            ("Approach", "One pass per case; a failure opens a defect with the case id"),
            ("Environments", "Staging with the release candidate build"),
            ("Risks", "Test data drift between runs"),
            ("Exit criteria", "Every case passed or its defect accepted"),
        )
    ]
    tables = [
        {
            "name": f"Values for {c['text']}",
            "columns": ["variant", "value", "expected"],
            "rows": [["baseline", "sample-1", "holds"], ["edge", "sample-2", "holds"]],
            "covers": [c["id"]],
        }
        for c in existing
        if not _instruction(c["text"])
    ]
    return {
        "cases": [],
        "gaps": [],
        "outline": outline,
        "data_tables": tables,
        "empty_reason": None,
        "rationale": "A five-section plan and one table per case.",
    }


def answer_tests(body: dict[str, Any]) -> dict[str, Any]:
    """Build provider-shaped cases or artefacts from the fenced story, criteria and cases."""
    turn = _turn(body)
    fields = _fields(turn)
    mode = MODE_LINE.search(turn)
    limit_match = MAX_CASES_LINE.search(turn)
    limit = int(limit_match.group("n")) if limit_match else 10
    if mode and mode.group("mode") == "artefacts":
        output = _artefacts(_lines(fields.get("cases", ""), CRITERION_LINE))
    else:
        criteria = _lines(fields.get("criteria", ""), CRITERION_LINE)
        arabic = _arabic(" ".join(c["text"] for c in criteria))
        output = _cases(criteria, fields.get("story", ""), limit, arabic)
    return envelope(body, json.dumps(output, ensure_ascii=False))


def answer_incident(body: dict[str, Any]) -> dict[str, Any]:
    """Build a provider-shaped post-mortem: every fact cited, factors by cue, actions from them."""
    turn = _turn(body)
    fields = _fields(turn)
    events = [
        e for e in _lines(fields.get("timeline", ""), EVENT_LINE) if not _instruction(e["text"])
    ]
    if not events:
        output: dict[str, Any] = {"empty_reason": "timeline_empty", "rationale": "No timeline."}
        return envelope(body, json.dumps(output, ensure_ascii=False))
    arabic = _arabic(" ".join(e["text"] for e in events))
    facts = [{"source_id": e["id"], "text": _first_sentence(e["text"])} for e in events]
    evidence = [e["id"] for e in events if any(cue in e["text"].lower() for cue in FACTOR_CUES)]
    factors = []
    if evidence:
        text = (
            "تغيير في النشر أو الإعداد سبق العطل"
            if arabic
            else "A deploy or configuration change preceded the failure"
        )
        factors.append({"text": text, "evidence": evidence})
    actions = [
        {
            "text": "أضف فحصاً قبل النشر للإعداد"
            if arabic
            else "Add a pre-deploy check for the configuration flag",
            "evidence": f["evidence"][:2],
            "confidence": ACTION_CONFIDENCE,
        }
        for f in factors
    ]
    first, last = events[0], events[-1]
    if arabic:
        summary = f"بدأ الحادث عند {first['at']} وانتهى عند {last['at']}. {facts[0]['text']}."
    else:
        summary = f"The incident ran from {first['at']} to {last['at']}. {facts[0]['text']}."
    tokens = sorted({e["token"] for e in events if e["token"]})
    output = {
        "summary": summary,
        "facts": facts,
        "contributing_factors": factors,
        "action_items": actions,
        "participants_mentioned": [t for t in tokens if t in summary],
        "empty_reason": None,
        "rationale": "Every entry restated with its id; one factor by cue; one action per factor.",
    }
    return envelope(body, json.dumps(output, ensure_ascii=False))
