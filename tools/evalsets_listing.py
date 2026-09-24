"""The interpret-query set's list-contract cases: STRATA lists, declared as the backend serves them.

Three lists as they are declared today — cycles (state; `-startsOn`), themes (state; `name`),
approvals (state; `-requestedAt`) — and cycles once their start-date range is declared
(`startsOnFrom` / `startsOnTo`, next loop). The sentences cover states, sorts, an undeclared field
("by budget"), a date the list cannot filter on yet, and Arabic with Arabic-Indic digits, which
must come back Latin. Each row of `CASES` is (id, locale, list, sentence, parameters, sort,
unresolved, tags). No case comes from tenant data.
"""

ORG = "11111111-1111-7111-8111-111111111111"
VERSION = "1.1.0"
NOW = "2026-09-24T01:30:00+03:00"


def _enum(param: str, values: list[str]) -> dict[str, object]:
    return {"param": param, "type": "enum", "values": values}


LISTS: dict[str, dict[str, object]] = {
    "cycles": {
        "filters": [_enum("state", ["planned", "active", "closed"])],
        "sorts": ["-startsOn"],
    },
    "themes": {"filters": [_enum("state", ["draft", "active", "retired"])], "sorts": ["name"]},
    "approvals": {
        "filters": [_enum("state", ["pending", "approved", "rejected"])],
        "sorts": ["-requestedAt"],
    },
    "cycles-ranged": {
        "filters": [
            _enum("state", ["planned", "active", "closed"]),
            {"param": "startsOnFrom", "type": "date"},
            {"param": "startsOnTo", "type": "date"},
        ],
        "sorts": ["-startsOn"],
    },
}
Row = tuple[str, str, str, str, dict[str, str], str | None, list[str], list[str]]
CASES: tuple[Row, ...] = (
    (
        "list-en-active-cycles",
        "en",
        "cycles",
        "active cycles",
        {"state": "active"},
        None,
        [],
        ["state"],
    ),
    ("list-en-themes-by-name", "en", "themes", "themes by name", {}, "name", [], ["sort"]),
    (
        "list-en-pending-approvals-newest",
        "en",
        "approvals",
        "pending approvals, newest first",
        {"state": "pending"},
        "-requestedAt",
        [],
        ["state", "sort"],
    ),
    ("list-en-by-budget", "en", "cycles", "cycles by budget", {}, None, ["budget"], ["undeclared"]),
    (
        "list-en-date-undeclared",
        "en",
        "cycles",
        "closed cycles after 2026-10-01",
        {"state": "closed"},
        None,
        ["after 2026-10-01"],
        ["undeclared", "date"],
    ),
    (
        "list-en-date-declared",
        "en",
        "cycles-ranged",
        "planned cycles after 2026-10-01",
        {"state": "planned", "startsOnFrom": "2026-10-01"},
        None,
        [],
        ["date"],
    ),
    (
        "list-ar-active-cycles",
        "ar",
        "cycles",
        "الدورات النشطة",
        {"state": "active"},
        None,
        [],
        ["state"],
    ),
    ("list-ar-themes-by-name", "ar", "themes", "المحاور حسب الاسم", {}, "name", [], ["sort"]),
    (
        "list-ar-pending-newest",
        "ar",
        "approvals",
        "الموافقات المعلقة الأحدث",
        {"state": "pending"},
        "-requestedAt",
        [],
        ["state", "sort"],
    ),
    (
        "list-ar-by-budget",
        "ar",
        "cycles",
        "الدورات حسب الميزانية",
        {},
        None,
        ["الميزانية"],
        ["undeclared"],
    ),
    (
        "list-ar-indic-digits",
        "ar",
        "cycles-ranged",
        "الدورات المخطط لها بعد ٢٠٢٦-١٠-٠١",
        {"state": "planned", "startsOnFrom": "2026-10-01"},
        None,
        [],
        ["date", "digits"],
    ),
)


def listing_cases() -> list[dict[str, object]]:
    """Return the list-contract cases, each with its declaration and the moment."""
    built: list[dict[str, object]] = []
    for case_id, locale, name, text, parameters, sort, unresolved, tags in CASES:
        request = {
            "organization_id": ORG,
            "capability_version": VERSION,
            "text": text,
            "listing": LISTS[name],
            "now": NOW,
            "timezone": "Asia/Riyadh",
            "locale": locale,
        }
        expected = {"query": "", "parameters": parameters, "sort": sort, "unresolved": unresolved}
        built.append(
            {
                "id": case_id,
                "input": request,
                "tags": [locale, "listing", *tags],
                "expected": expected,
            }
        )
    return built
