"""The standup and digest cases of the summarize set: a window, tokens, kinds and counts."""

from datetime import UTC, datetime, timedelta

from tools.thread_terms import ORG, TOPIC_AR, TOPICS, VERSION
from tools.window_terms import (
    DIGEST_LINES_AR,
    DIGEST_LINES_EN,
    KINDS,
    STANDUP_LINES_AR,
    STANDUP_LINES_EN,
    WINDOW_INJECTIONS,
)

START = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)
WINDOW_HOURS = 24
LENGTHS = (3, 6, 12, 24)
PARTICIPANTS = 4
OUTSIDE_EVERY = 3
COUNT_OFFSET = 11


def _window(seed: int) -> dict[str, str]:
    start = START + timedelta(days=seed)
    return {"from_at": start.isoformat(), "to_at": (start + timedelta(hours=24)).isoformat()}


def _at(seed: int, index: int, outside: bool) -> str:
    start = START + timedelta(days=seed)
    offset = timedelta(hours=WINDOW_HOURS + 2) if outside else timedelta(minutes=index * 37)
    return (start + offset).isoformat()


def _case(
    case_id: str, request: dict[str, object], tags: list[str], expected: dict[str, object]
) -> dict[str, object]:
    return {"id": case_id, "input": request, "tags": tags, "expected": expected}


def _request(
    mode: str, seed: int, items: list[dict[str, object]], **extra: object
) -> dict[str, object]:
    request: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "mode": mode,
        "items": items,
        "window": _window(seed),
        "target_words": 120,
    }
    request.update(extra)
    return request


def _split(items: list[dict[str, object]], spill: bool) -> tuple[list[str], list[str]]:
    inside, outside = [], []
    for index, item in enumerate(items):
        if spill and index % OUTSIDE_EVERY == OUTSIDE_EVERY - 1:
            outside.append(str(item["id"]))
        else:
            inside.append(str(item["id"]))
    return inside, outside


def _standup_items(
    count: int, topic: str, arabic: bool, seed: int, spill: bool
) -> list[dict[str, object]]:
    lines = STANDUP_LINES_AR if arabic else STANDUP_LINES_EN
    items: list[dict[str, object]] = []
    for index in range(count):
        outside = spill and index % OUTSIDE_EVERY == OUTSIDE_EVERY - 1
        text = lines[(seed + index) % len(lines)].format(
            topic=topic, topic_ar=TOPIC_AR[topic], n=200 + seed + index, build=5_000 + seed
        )
        items.append(
            {
                "id": f"u{seed}-{index + 1}",
                "participant": f"p{(seed + index) % PARTICIPANTS + 1}",
                "at": _at(seed, index, outside),
                "text": text,
                "kind": "update",
            }
        )
    return items


def _digest_items(
    count: int, topic: str, arabic: bool, seed: int, spill: bool
) -> list[dict[str, object]]:
    table = DIGEST_LINES_AR if arabic else DIGEST_LINES_EN
    items: list[dict[str, object]] = []
    for index in range(count):
        kind = KINDS[(seed + index) % len(KINDS)]
        lines = table[kind]
        outside = spill and index % OUTSIDE_EVERY == OUTSIDE_EVERY - 1
        text = lines[(seed + index) % len(lines)].format(
            topic=topic, topic_ar=TOPIC_AR[topic], n=300 + seed + index, build=5_000 + seed
        )
        items.append(
            {
                "id": f"d{seed}-{index + 1}",
                "participant": f"p{(seed + index) % PARTICIPANTS + 1}",
                "at": _at(seed, index, outside),
                "text": text,
                "kind": kind,
            }
        )
    return items


def _counts(items: list[dict[str, object]], seed: int) -> list[dict[str, object]]:
    """Return the backend's counts — deliberately not the number of items sent, so an echo shows."""
    kinds = sorted({str(item["kind"]) for item in items})
    return [
        {"kind": kind, "count": COUNT_OFFSET + seed + index} for index, kind in enumerate(kinds)
    ] + [{"kind": "test_plan", "count": 0}]


def _window_case(
    mode: str, topic: tuple[str, str, str], length: int, seed: int
) -> dict[str, object]:
    _, _, name = topic
    arabic = seed % 5 == 0
    spill = seed % 2 == 0
    build = _standup_items if mode == "standup" else _digest_items
    items = build(length, name, arabic, seed, spill)
    inside, outside = _split(items, spill)
    extra: dict[str, object] = {}
    if mode == "digest":
        extra["counts"] = _counts(items, seed)
    request = _request(mode, seed, items, **extra)
    tags = [mode, "ar" if arabic else "en", f"length:{length}"] + (["spill"] if spill else [])
    expected: dict[str, object] = {
        "script": "ARABIC" if arabic else "LATIN",
        "inside_ids": inside,
        "outside_ids": outside,
    }
    return _case(f"{mode}-{name}-{length}", request, tags, expected)


def _injection_window_cases(mode: str, seed: int) -> list[dict[str, object]]:
    cases = []
    build = _standup_items if mode == "standup" else _digest_items
    for index, injection in enumerate(WINDOW_INJECTIONS):
        items = build(4, TOPICS[index][2], False, seed + index, False)
        items[2]["text"] = injection
        extra: dict[str, object] = {"counts": _counts(items, seed)} if mode == "digest" else {}
        cases.append(
            _case(
                f"{mode}-injection-{index}",
                _request(mode, seed + index, items, **extra),
                [mode, "en", "injection"],
                {"script": "LATIN", "inside_ids": [str(i["id"]) for i in items], "outside_ids": []},
            )
        )
    return cases


def _empty_window_cases(mode: str, seed: int) -> list[dict[str, object]]:
    build = _standup_items if mode == "standup" else _digest_items
    items = build(3, TOPICS[0][2], False, seed, False)
    for item in items:
        item["at"] = _at(seed, 0, True)
    extra: dict[str, object] = {"counts": _counts(items, seed)} if mode == "digest" else {}
    return [
        _case(
            f"{mode}-empty",
            _request(mode, seed, [], **extra),
            [mode, "empty"],
            {"empty": True, "inside_ids": [], "outside_ids": []},
        ),
        _case(
            f"{mode}-all-outside",
            _request(mode, seed, items, **extra),
            [mode, "empty", "spill"],
            {"empty": True, "inside_ids": [], "outside_ids": [str(i["id"]) for i in items]},
        ),
    ]


def window_cases() -> list[dict[str, object]]:
    """Standups and digests over ten topics and four lengths; injections; empty windows."""
    cases: list[dict[str, object]] = []
    seed = 100
    for mode in ("standup", "digest"):
        for topic in TOPICS:
            for length in LENGTHS:
                seed += 1
                cases.append(_window_case(mode, topic, length, seed))
        cases += _injection_window_cases(mode, seed + 1)
        cases += _empty_window_cases(mode, seed + 10)
        seed += 20
    return cases
