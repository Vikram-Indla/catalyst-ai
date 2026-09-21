"""`python -m tools.evalsets summarize|translate`: the synthetic summary and translation sets."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import rules
from tools.evalsets_windows import window_cases
from tools.thread_terms import (
    COMMENT_LINES_AR,
    COMMENT_LINES_EN,
    FIELD_TEXTS_AR,
    FIELD_TEXTS_EN,
    INJECTION_COMMENTS,
    ORG,
    STATUS_PAIRS,
    TITLES_AR,
    TITLES_EN,
    TOPIC_AR,
    TOPICS,
    TRANSLATE_INJECTIONS,
    VERSION,
)

START = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
LENGTHS = (1, 2, 3, 5, 8, 12, 20, 30, 40)
LONG_THREAD = 20
ARABIC_INJECTION = 2


def _case(
    case_id: str, request: dict[str, object], tags: list[str], expected: dict[str, object]
) -> dict[str, object]:
    return {"id": case_id, "input": request, "tags": tags, "expected": expected}


def _items(count: int, topic: str, arabic: bool, seed: int) -> list[dict[str, object]]:
    lines = COMMENT_LINES_AR if arabic else COMMENT_LINES_EN
    items: list[dict[str, object]] = []
    for index in range(count):
        line = lines[(seed + index) % len(lines)]
        text = line.format(topic=topic, topic_ar=TOPIC_AR[topic], n=100 + seed, build=4_100 + seed)
        items.append(
            {
                "id": f"c{seed}-{index + 1}",
                "participant": f"p{(seed + index) % 4 + 1}",
                "at": (START + timedelta(hours=seed, minutes=index * 7)).isoformat(),
                "text": text,
            }
        )
    return items


def _status_changes(seed: int, count: int) -> list[dict[str, object]]:
    changes: list[dict[str, object]] = []
    for index in range(count):
        old, new = STATUS_PAIRS[(seed + index) % len(STATUS_PAIRS)]
        changes.append(
            {
                "participant": f"p{index % 3 + 1}",
                "from_status": old,
                "to_status": new,
                "at": (START + timedelta(hours=seed, minutes=index * 11 + 3)).isoformat(),
            }
        )
    return changes


def _summarize_request(mode: str, **extra: object) -> dict[str, object]:
    request: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "mode": mode,
    }
    request.update(extra)
    return request


def _thread_case(
    mode: str, topic: tuple[str, str, str], length: int, seed: int
) -> dict[str, object]:
    item_type, title, name = topic
    arabic = seed % 5 == 0
    changes = _status_changes(seed, 2) if mode == "comments" and seed % 3 == 0 else []
    target = (80, 150, 220, 400)[seed % 4]
    request = _summarize_request(
        mode,
        items=_items(length, name, arabic, seed),
        item_title=title if mode == "comments" else None,
        item_type=item_type if mode == "comments" else None,
        status_changes=changes,
        target_words=target,
    )
    tags = [mode, "ar" if arabic else "en", f"length:{length}"]
    tags += ["status"] if changes else []
    tags += ["long"] if length >= LONG_THREAD else []
    expected: dict[str, object] = {
        "script": "ARABIC" if arabic else "LATIN",
        "target_words": target,
    }
    return _case(f"{mode}-{name}-{length}", request, tags, expected)


def _injection_thread_cases(mode: str, seed: int) -> list[dict[str, object]]:
    cases = []
    for index, injection in enumerate(INJECTION_COMMENTS):
        items = _items(4, TOPICS[index][2], False, seed + index)
        items[2]["text"] = injection
        cases.append(
            _case(
                f"{mode}-injection-{index}",
                _summarize_request(mode, items=items, target_words=120),
                [mode, "en", "injection"],
                {"script": "LATIN", "target_words": 120},
            )
        )
    return cases


def summarize_cases() -> list[dict[str, object]]:
    """Comment and discussion threads: lengths, scripts, status changes, empties, injection."""
    cases: list[dict[str, object]] = []
    seed = 0
    for mode in ("comments", "thread", "chat"):
        for topic_index, topic in enumerate(TOPICS):
            for length in LENGTHS[: 4 if mode != "comments" else 5]:
                seed += 1
                cases.append(_thread_case(mode, topic, length, seed))
            if topic_index % 3 == 0:
                item_type, title, name = topic
                empty = _summarize_request(mode, items=[], item_title=title, item_type=item_type)
                cases.append(_case(f"{mode}-{name}-empty", empty, [mode, "empty"], {"empty": True}))
        cases += _injection_thread_cases(mode, seed + 1)
        seed += len(INJECTION_COMMENTS)
    return cases + window_cases()


def _translate_request(mode: str, text: str, target: str, **extra: object) -> dict[str, object]:
    request: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "mode": mode,
        "text": text,
        "target_language": target,
    }
    request.update(extra)
    return request


def _field_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    seed = 0
    for direction, sources, target in (
        ("en-ar", FIELD_TEXTS_EN, "ar"),
        ("ar-en", FIELD_TEXTS_AR, "en"),
    ):
        for index, template in enumerate(sources):
            for variant in range(4):
                seed += 1
                text = template.format(n=100 + seed, m=200 + seed, build=4_100 + seed)
                if variant == 1:
                    text = text + f"\n\nNote {seed}: keep `code_{seed}` and PRJ-{300 + seed}."
                if variant == 2:
                    text = text.replace("\n\n", "\n\n\n")
                context = "A work item in a software project." if variant == 3 else None
                request = _translate_request("field", text, target, context=context)
                expected: dict[str, object] = {"target": target, "source": direction.split("-")[0]}
                cases.append(
                    _case(
                        f"field-{direction}-{index}-{variant}",
                        request,
                        ["field", direction],
                        expected,
                    )
                )
    return cases


def _title_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    seed = 500
    for direction, sources, target in (("en-ar", TITLES_EN, "ar"), ("ar-en", TITLES_AR, "en")):
        for index, template in enumerate(sources):
            for variant in range(3):
                seed += 1
                text = template.format(n=100 + seed)
                if variant == 2:
                    text = text + f" (PRJ-{400 + seed})"
                request = _translate_request("title", text, target)
                expected: dict[str, object] = {"target": target, "source": direction.split("-")[0]}
                cases.append(
                    _case(
                        f"title-{direction}-{index}-{variant}",
                        request,
                        ["title", direction],
                        expected,
                    )
                )
    return cases


def _injection_translate_cases() -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for index, injection in enumerate(TRANSLATE_INJECTIONS):
        target = "en" if index == ARABIC_INJECTION else "ar"
        expected: dict[str, object] = {
            "target": target,
            "source": "ar" if index == ARABIC_INJECTION else "en",
        }
        field = _translate_request("field", injection, target)
        title = _translate_request("title", injection.split(".")[0], target)
        cases.append(_case(f"field-injection-{index}", field, ["field", "injection"], expected))
        cases.append(_case(f"title-injection-{index}", title, ["title", "injection"], expected))
    return cases


def translate_cases() -> list[dict[str, object]]:
    """Fields and titles in both directions, with Markdown, keys, code and links; injections."""
    return _field_cases() + _title_cases() + _injection_translate_cases()


def write_threads(name: str) -> int:
    """Write `set.jsonl` for the summarize or translate set."""
    cases = summarize_cases() if name == "summarize" else translate_cases()
    (Path(rules.EVALS) / name / "set.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8"
    )
    print(f"wrote {len(cases)} cases for {name}")
    return 0
