"""`python -m tools.evalsets release-notes|generate-tests|post-mortem`: the hub sets."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import rules
from tools.hub_terms import (
    CHANGE_KINDS,
    CHANGE_LINES_AR,
    CHANGE_LINES_EN,
    CRITERIA_AR,
    CRITERIA_EN,
    INCIDENT_INJECTIONS,
    INCIDENT_TOPICS,
    INCIDENTS,
    ORG,
    RELEASE_INJECTIONS,
    RELEASES,
    STORIES,
    TEST_INJECTIONS,
    TIMELINE_AR,
    TIMELINE_EN,
    TOPIC_AR,
    VAGUE_CRITERIA,
    VERSION,
)

START = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)
CHANGE_SIZES = (3, 8, 15, 30)
CRITERIA_SIZES = (3, 5, 8, 12)
CASE_SIZES = (3, 5, 8, 10)
TIMELINE_SIZES = (3, 6, 12, 20)
NOT_DONE_EVERY = 4
ARABIC_EVERY = 5
CATEGORIES = ("todo", "in_progress")


def _case(
    case_id: str, request: dict[str, object], tags: list[str], expected: dict[str, object]
) -> dict[str, object]:
    return {"id": case_id, "input": request, "tags": tags, "expected": expected}


def _base(**fields: object) -> dict[str, object]:
    request: dict[str, object] = {"organization_id": ORG, "capability_version": VERSION}
    request.update(fields)
    return request


def _changes(count: int, arabic: bool, seed: int) -> list[dict[str, object]]:
    table = CHANGE_LINES_AR if arabic else CHANGE_LINES_EN
    changes: list[dict[str, object]] = []
    for index in range(count):
        kind = CHANGE_KINDS[(seed + index) % len(CHANGE_KINDS)]
        titles = table[kind]
        not_done = index % NOT_DONE_EVERY == NOT_DONE_EVERY - 1
        changes.append(
            {
                "id": f"chg-{seed}-{index + 1}",
                "key": f"PRJ-{400 + seed + index}",
                "kind": kind,
                "title": titles[(seed + index) % len(titles)],
                "status_category": CATEGORIES[index % 2] if not_done else "done",
                "participant": f"p{index % 3 + 1}" if index % 2 == 0 else None,
            }
        )
    return changes


def _release_case(mode: str, index: int, size: int, seed: int) -> dict[str, object]:
    name, version, date = RELEASES[index]
    arabic = seed % ARABIC_EVERY == 0
    changes = _changes(size, arabic, seed)
    audience = "customer" if seed % 2 == 0 else "internal"
    request = _base(
        mode=mode,
        release={"name": name, "version": version, "target_date": date, "status": "planned"},
        changes=changes,
        audience=audience,
    )
    done = [str(c["id"]) for c in changes if c["status_category"] == "done"]
    tags = [mode, audience, "ar" if arabic else "en", f"size:{size}"]
    empty = mode == "notes" and not done
    expected: dict[str, object] = {
        "script": "ARABIC" if arabic else "LATIN",
        "done_ids": done,
        "empty": empty,
    }
    return _case(f"{mode}-{name.lower().replace(' ', '-')}-{size}", request, tags, expected)


def _release_injections(mode: str, seed: int) -> list[dict[str, object]]:
    cases = []
    for index, injection in enumerate(RELEASE_INJECTIONS):
        changes = _changes(6, False, seed + index)
        changes[2]["title"] = injection
        name, version, date = RELEASES[index]
        request = _base(
            mode=mode,
            release={"name": name, "version": version, "target_date": date},
            changes=changes,
            audience="internal",
        )
        done = [str(c["id"]) for c in changes if c["status_category"] == "done"]
        cases.append(
            _case(
                f"{mode}-injection-{index}",
                request,
                [mode, "en", "injection"],
                {"script": "LATIN", "done_ids": done, "empty": False},
            )
        )
    return cases


def release_cases() -> list[dict[str, object]]:
    """Build notes and overviews over ten releases and four sizes; injections; an empty one."""
    cases: list[dict[str, object]] = []
    seed = 0
    for mode in ("notes", "summary"):
        for index in range(len(RELEASES)):
            for size in CHANGE_SIZES:
                seed += 1
                cases.append(_release_case(mode, index, size, seed))
        cases += _release_injections(mode, seed + 1)
        name, version, _ = RELEASES[0]
        empty = _base(mode=mode, release={"name": name, "version": version}, changes=[])
        cases.append(_case(f"{mode}-empty", empty, [mode, "empty"], {"empty": True}))
    return cases


def _criteria(count: int, arabic: bool, seed: int, vague: bool) -> list[dict[str, object]]:
    lines = CRITERIA_AR if arabic else CRITERIA_EN
    criteria: list[dict[str, object]] = [
        {"id": f"ac-{seed}-{i + 1}", "text": lines[(seed + i) % len(lines)]} for i in range(count)
    ]
    if vague:
        criteria[-1] = {"id": f"ac-{seed}-{count}", "text": VAGUE_CRITERIA[seed % 3]}
    return criteria


def _existing_cases(count: int, seed: int) -> list[dict[str, object]]:
    return [
        {
            "id": f"tc-{seed}-{i + 1}",
            "title": f"Verify {CRITERIA_EN[(seed + i) % len(CRITERIA_EN)].lower()}",
            "objective": CRITERIA_EN[(seed + i) % len(CRITERIA_EN)],
            "steps": [
                {"action": "Open the page", "expected": "The page loads"},
                {"action": "Do the thing under test", "expected": "The criterion holds"},
            ],
        }
        for i in range(count)
    ]


def _tests_case(mode: str, index: int, size: int, seed: int) -> dict[str, object]:
    title, description = STORIES[index]
    arabic = seed % ARABIC_EVERY == 0 and mode == "cases"
    vague = seed % 3 == 0 and mode == "cases"
    story = {"key": f"PRJ-{500 + seed}", "title": title, "description": description}
    if mode == "cases":
        request = _base(mode=mode, story=story, criteria=_criteria(size, arabic, seed, vague))
    else:
        request = _base(mode=mode, story=story, cases=_existing_cases(size, seed))
    tags = [mode, "ar" if arabic else "en", f"size:{size}"] + (["vague"] if vague else [])
    expected: dict[str, object] = {
        "script": "ARABIC" if arabic else "LATIN",
        "empty": False,
        "vague": vague,
    }
    return _case(f"{mode}-{title.lower().replace(' ', '-')}-{size}", request, tags, expected)


def _tests_injections(mode: str, seed: int) -> list[dict[str, object]]:
    cases = []
    for index, injection in enumerate(TEST_INJECTIONS):
        title, description = STORIES[index]
        story = {"key": f"PRJ-{600 + index}", "title": title, "description": description}
        expected: dict[str, object] = {"script": "LATIN", "empty": False, "vague": False}
        if mode == "cases":
            criteria = _criteria(4, False, seed + index, False)
            criteria[1]["text"] = injection
            expected["injected_ids"] = [criteria[1]["id"]]
            request = _base(mode=mode, story=story, criteria=criteria)
        else:
            existing = _existing_cases(4, seed + index)
            existing[1]["title"] = injection
            request = _base(mode=mode, story=story, cases=existing)
        cases.append(
            _case(f"{mode}-injection-{index}", request, [mode, "en", "injection"], expected)
        )
    return cases


def tests_cases() -> list[dict[str, object]]:
    """Cases from criteria and artefacts from cases, ten stories × four sizes; injections."""
    cases: list[dict[str, object]] = []
    seed = 0
    for mode, sizes in (("cases", CRITERIA_SIZES), ("artefacts", CASE_SIZES)):
        for index in range(len(STORIES)):
            for size in sizes:
                seed += 1
                cases.append(_tests_case(mode, index, size, seed))
        cases += _tests_injections(mode, seed + 1)
    title, _ = STORIES[0]
    bare = _base(mode="cases", story={"title": title}, criteria=[])
    cases.append(_case("cases-empty", bare, ["cases", "empty"], {"empty": True, "vague": False}))
    return cases


def _timeline(count: int, topic: str, arabic: bool, seed: int) -> list[dict[str, object]]:
    lines = TIMELINE_AR if arabic else TIMELINE_EN
    return [
        {
            "id": f"ev-{seed}-{i + 1}",
            "at": (START + timedelta(days=seed, minutes=i * 9)).isoformat(),
            "participant": f"p{i % 4 + 1}",
            "text": lines[(seed + i) % len(lines)].format(
                topic=topic, topic_ar=TOPIC_AR[topic], build=7_000 + seed, n=700 + seed
            ),
        }
        for i in range(count)
    ]


def _incident_case(index: int, size: int, seed: int) -> dict[str, object]:
    title, severity = INCIDENTS[index]
    topic = INCIDENT_TOPICS[index]
    arabic = seed % ARABIC_EVERY == 0
    timeline = _timeline(size, topic, arabic, seed)
    incident = {"key": f"INC-{100 + seed}", "title": title, "severity": severity}
    request = _base(incident=incident, timeline=timeline)
    tags = ["ar" if arabic else "en", f"size:{size}", severity]
    expected: dict[str, object] = {
        "script": "ARABIC" if arabic else "LATIN",
        "empty": False,
        "event_ids": [str(e["id"]) for e in timeline],
    }
    return _case(f"{topic}-{size}", request, tags, expected)


def incident_cases() -> list[dict[str, object]]:
    """Post-mortems over ten incidents and four timeline lengths; injections; an empty timeline."""
    cases: list[dict[str, object]] = []
    seed = 0
    for index in range(len(INCIDENTS)):
        for size in TIMELINE_SIZES:
            seed += 1
            cases.append(_incident_case(index, size, seed))
    for index, injection in enumerate(INCIDENT_INJECTIONS):
        timeline = _timeline(5, INCIDENT_TOPICS[index], False, seed + index + 1)
        timeline[2]["text"] = injection
        title, severity = INCIDENTS[index]
        request = _base(incident={"title": title, "severity": severity}, timeline=timeline)
        expected = {
            "script": "LATIN",
            "empty": False,
            "event_ids": [str(e["id"]) for e in timeline],
        }
        cases.append(_case(f"injection-{index}", request, ["en", "injection"], expected))
    title, severity = INCIDENTS[0]
    empty = _base(incident={"title": title, "severity": severity}, timeline=[])
    cases.append(_case("empty", empty, ["empty"], {"empty": True, "event_ids": []}))
    return cases


def write_hub(name: str) -> int:
    """Write `set.jsonl` for a hub set."""
    builders = {
        "release-notes": release_cases,
        "generate-tests": tests_cases,
        "post-mortem": incident_cases,
    }
    cases = builders[name]()
    (Path(rules.EVALS) / name / "set.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8"
    )
    print(f"wrote {len(cases)} cases for {name}")
    return 0
