"""The authored stand-in for brief: a grounded briefing read back from the rendered chain.

Deterministic and well-behaved, like every stand-in: every sentence cites the ids it rests on,
states only numbers the chain carries, names which health it means every time, says "not
measured" where the chain does, and never echoes the charter, where an instruction may hide.
"""

import json
import re
from typing import Any

from tools.authored_envelope import envelope

FENCE = re.compile(r"<<<chain>>>\n(?P<body>.*?)\n<<<end chain>>>", re.S)
LANGUAGE = re.compile(r"^Language: (?P<language>\w+)$", re.M)
LIMIT = re.compile(r"^Summary length: at most (?P<n>\d) sentences$", re.M)
THEME = re.compile(r"^theme \[(?P<id>[^\]]+)\]: (?P<title>.+)$", re.M)
OBJECTIVE = re.compile(
    r"^objective \[(?P<id>[^\]]+)\] status (?P<status>\w+), "
    r"progress (?P<progress>[^:]+): (?P<title>.+)$",
    re.M,
)
KEY_RESULT = re.compile(
    r"^  key result \[(?P<id>[^\]]+)\] value (?P<value>[^,]+),.*?: (?P<title>.+)$", re.M
)
PROJECT = re.compile(
    r"^project \[(?P<id>[^\]]+)\] delivery health (?P<delivery>\w+), strategic health "
    r"(?P<strategic>\w+)(?P<blocked>, blocked)?: (?P<title>.+)$",
    re.M,
)
FINDING = re.compile(r"^finding \[(?P<id>[^\]]+)\] severity (?P<severity>\w+): ", re.M)
NOT_MEASURED = "not measured"
TROUBLE = ("at_risk", "off_track")
PHRASES = {
    "en": {
        "on_track": "on track",
        "at_risk": "at risk",
        "off_track": "off track",
        "not_measured": "not measured",
    },
    "ar": {
        "on_track": "على المسار",
        "at_risk": "معرّض للخطر",
        "off_track": "خارج المسار",
        "not_measured": "غير مقاس",
    },
}
SAY = {
    "en": {
        "theme": "{title}: this briefing covers its objectives, projects and findings.",
        "measured": "{title} has strategic status {status}, at {progress} progress.",
        "unmeasured": "{title} has strategic status {status}; its progress is not measured.",
        "project": "{title}: delivery health {delivery}, strategic health {strategic}.",
        "blocked": "{title} is blocked: delivery health {delivery}, strategic health {strategic}.",
        "finding": "A high-severity finding is open against the theme.",
        "unblock": "Unblock {title}.",
        "measure": "Set a measurement for {title}.",
        "gap": "some key results are not measured",
        "why": "Briefed from the chain's official figures only.",
    },
    "ar": {
        "theme": "«{title}»: يغطي هذا الموجز أهدافه ومشاريعه وملاحظاته.",
        "measured": "الهدف «{title}» حالته الاستراتيجية {status} بتقدم {progress}.",
        "unmeasured": "الهدف «{title}» حالته الاستراتيجية {status}، والتقدم غير مقاس.",
        "project": "المشروع «{title}»: صحة التسليم {delivery}، والصحة الاستراتيجية {strategic}.",
        "blocked": (
            "المشروع «{title}» متوقف: صحة التسليم {delivery}، والصحة الاستراتيجية {strategic}."
        ),
        "finding": "توجد ملاحظة عالية الخطورة مفتوحة على المحور.",
        "unblock": "رفع التوقف عن «{title}».",
        "measure": "تحديد قياس لـ «{title}».",
        "gap": "بعض النتائج الرئيسية غير مقاسة",
        "why": "أُعد الموجز من الأرقام الرسمية في السلسلة فقط.",
    },
}


def _sentence(text: str, *cites: str) -> dict[str, Any]:
    return {"text": text, "cites": list(cites)}


def _objective(
    match: re.Match[str], say: dict[str, str], phrases: dict[str, str]
) -> dict[str, Any]:
    status = phrases[match.group("status")]
    progress = match.group("progress").strip()
    template = say["unmeasured"] if progress == NOT_MEASURED else say["measured"]
    text = template.format(title=match.group("title"), status=status, progress=progress)
    return _sentence(text, match.group("id"))


def _project(match: re.Match[str], say: dict[str, str], phrases: dict[str, str]) -> dict[str, Any]:
    template = say["blocked"] if match.group("blocked") else say["project"]
    text = template.format(
        title=match.group("title"),
        delivery=phrases[match.group("delivery")],
        strategic=phrases[match.group("strategic")],
    )
    return _sentence(text, match.group("id"))


def brief(chain: str, locale: str, limit: int) -> dict[str, Any]:
    """Return the briefing's JSON for a rendered chain."""
    say, phrases = SAY[locale], PHRASES[locale]
    theme = THEME.search(chain)
    objectives = list(OBJECTIVE.finditer(chain))
    projects = list(PROJECT.finditer(chain))
    output: dict[str, Any] = {
        "summary": [],
        "highlights": [],
        "risks": [],
        "asks": [],
        "unsupported": [],
    }
    if theme is None or not (objectives or projects or FINDING.search(chain)):
        return {**output, "empty_reason": "nothing_to_brief", "rationale": say["why"]}
    summary = [_sentence(say["theme"].format(title=theme.group("title")), theme.group("id"))]
    summary += [_objective(match, say, phrases) for match in objectives]
    output["summary"] = summary[:limit]
    for match in objectives:
        bucket = "risks" if match.group("status") in TROUBLE else "highlights"
        output[bucket].append(_objective(match, say, phrases))
    for match in projects:
        troubled = match.group("blocked") or match.group("delivery") in TROUBLE
        output["risks" if troubled else "highlights"].append(_project(match, say, phrases))
        if match.group("blocked"):
            output["asks"].append(
                _sentence(say["unblock"].format(title=match.group("title")), match.group("id"))
            )
    for match in FINDING.finditer(chain):
        if match.group("severity") == "high":
            output["risks"].append(_sentence(say["finding"], match.group("id")))
    unmeasured = [m for m in KEY_RESULT.finditer(chain) if m.group("value").strip() == NOT_MEASURED]
    output["asks"] += [
        _sentence(say["measure"].format(title=m.group("title")), m.group("id")) for m in unmeasured
    ]
    output["unsupported"] = [say["gap"]] if unmeasured else []
    return {**output, "empty_reason": None, "rationale": say["why"]}


def answer_brief(body: dict[str, Any]) -> dict[str, Any]:
    """Build the provider-shaped answer for a brief request."""
    turn = "".join(part.get("text", "") for part in body["contents"][0]["parts"])
    fenced = FENCE.search(turn)
    language = LANGUAGE.search(turn)
    limit = LIMIT.search(turn)
    locale = "ar" if language and language.group("language") == "Arabic" else "en"
    output = brief(
        fenced.group("body") if fenced else "", locale, int(limit.group("n")) if limit else 5
    )
    return envelope(body, json.dumps(output, ensure_ascii=False))
