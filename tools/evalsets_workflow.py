"""`python -m tools.evalsets propose-workflow`: the synthetic workflow set from process families."""

import json
from pathlib import Path

from tools import rules
from tools.workflow_terms import (
    GUARD_PHRASES,
    INJECTIONS,
    KIND_PHRASES_AR,
    KIND_PHRASES_EN,
    ORG,
    PROCESSES,
    TERMINALS,
    VAGUE,
    VERSION,
    Move,
    Stage,
)

WAITING = frozenset({"parked", "ready", "blocked", "scheduled"})
REASON_KINDS = frozenset({"backward", "reject", "reopen"})
EXISTING_STAGES = 2


def _label(stage: Stage, arabic: bool) -> str:
    return stage[2] if arabic else stage[1]


def _labels(stages: list[Stage], arabic: bool) -> dict[str, str]:
    return {stage[0]: _label(stage, arabic) for stage in stages}


def _guard_phrase(guard: str | None, arabic: bool) -> str:
    if guard is None:
        return ""
    return " " + GUARD_PHRASES[guard][1 if arabic else 0]


def _move_sentence(move: Move, labels: dict[str, str], arabic: bool) -> str:
    source, target, kind, guard = move
    if source is None:
        template = "يمكن إلغاء أي عنصر كـ {b}." if arabic else "Any item can be cancelled as {b}."
        return template.format(b=labels[target])
    if kind == "forward":
        template = "من {a} ينتقل إلى {b}{g}." if arabic else "From {a} it moves to {b}{g}."
        return template.format(a=labels[source], b=labels[target], g=_guard_phrase(guard, arabic))
    phrases = KIND_PHRASES_AR if arabic else KIND_PHRASES_EN
    return phrases[kind].format(a=labels[source], b=labels[target])


def describe(name: str, stages: list[Stage], moves: list[Move], arabic: bool, guards: bool) -> str:
    """Write the process out as the sentences an admin would use, one fact per sentence."""
    labels = _labels(stages, arabic)
    start = "يبدأ كـ {s}." if arabic else "It starts as {s}."
    end = "ينتهي كـ {s}." if arabic else "It ends as {s}."
    waiting = "{s} حالة انتظار." if arabic else "{s} is a waiting state."
    sentences = [start.format(s=labels[stages[0][0]])]
    for move in moves:
        stripped: Move = (move[0], move[1], move[2], move[3] if guards else None)
        sentences.append(_move_sentence(stripped, labels, arabic))
    sentences += [end.format(s=labels[key]) for key in TERMINALS[name]]
    sentences += [waiting.format(s=labels[k]) for k, _, _ in stages if k in WAITING]
    return " ".join(sentences)


def _request(description: str, **extra: object) -> dict[str, object]:
    request: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "description": description,
    }
    request.update(extra)
    return request


def _expected(name: str, stages: list[Stage], moves: list[Move], guards: bool) -> dict[str, object]:
    return {
        "stage_keys": [stage[0] for stage in stages],
        "terminal_keys": list(TERMINALS[name]),
        "kinds": sorted({move[2] for move in moves}),
        "reason_moves": sum(1 for move in moves if move[2] in REASON_KINDS),
        "guards": sorted({m[3] for m in moves if m[3]}) if guards else [],
        "empty": False,
    }


def _existing(stages: list[Stage], moves: list[Move]) -> dict[str, object]:
    kept = stages[:EXISTING_STAGES]
    keys = {stage[0] for stage in kept}
    return {
        "statuses": [
            {
                "key": key,
                "name": label,
                "category": "todo",
                "initial": index == 0,
                "terminal": False,
                "order": index,
            }
            for index, (key, label, _) in enumerate(kept)
        ],
        "transitions": [
            {
                "from_key": source,
                "to_key": target,
                "kind": kind,
                "guards": [],
                "reason_code": None,
                "rationale": "Already in the scheme.",
            }
            for source, target, kind, _ in moves
            if source in keys and target in keys
        ],
    }


def _case(
    case_id: str, request: dict[str, object], tags: list[str], expected: dict[str, object]
) -> dict[str, object]:
    return {"id": case_id, "input": request, "tags": tags, "expected": expected}


def _family_cases(name: str) -> list[dict[str, object]]:
    stages, moves = PROCESSES[name]
    vocabulary = list(GUARD_PHRASES)
    plain = describe(name, stages, moves, False, False)
    guarded = describe(name, stages, moves, False, True)
    arabic = describe(name, stages, moves, True, True)
    expected = _expected(name, stages, moves, False)
    return [
        _case(f"{name}-plain", _request(plain, item_type=name), ["en", "plain"], expected),
        _case(
            f"{name}-guards",
            _request(guarded, item_type=name, guard_vocabulary=vocabulary),
            ["en", "guards"],
            _expected(name, stages, moves, True),
        ),
        _case(
            f"{name}-existing",
            _request(plain, item_type=name, existing=_existing(stages, moves)),
            ["en", "existing"],
            expected,
        ),
        _case(
            f"{name}-two-categories",
            _request(plain, item_type=name, allowed_categories=["todo", "done"]),
            ["en", "categories"],
            expected,
        ),
        _case(
            f"{name}-ar",
            _request(arabic, item_type=name, guard_vocabulary=vocabulary, language="ar"),
            ["ar", "guards"],
            {**_expected(name, stages, moves, True), "script": "ARABIC"},
        ),
        _case(
            f"{name}-guards-unknown",
            _request(guarded, item_type=name, guard_vocabulary=vocabulary[:1]),
            ["en", "guards", "vocabulary"],
            {
                **_expected(name, stages, moves, True),
                "guards": sorted({m[3] for m in moves if m[3] in vocabulary[:1]}),
            },
        ),
    ]


def _injection_cases() -> list[dict[str, object]]:
    names = list(PROCESSES)
    cases = []
    for index, injection in enumerate(INJECTIONS):
        name = names[index % len(names)]
        stages, moves = PROCESSES[name]
        text = describe(name, stages, moves, False, False) + " " + injection
        cases.append(
            _case(
                f"injection-{index}",
                _request(text, item_type=name),
                ["en", "injection"],
                _expected(name, stages, moves, False),
            )
        )
    return cases


def _vague_cases() -> list[dict[str, object]]:
    return [
        _case(f"vague-{index}", _request(text), ["en", "vague"], {"empty": True})
        for index, text in enumerate(VAGUE)
    ]


def workflow_cases() -> list[dict[str, object]]:
    """Six families, six variations each; injections; vague descriptions that yield nothing."""
    cases: list[dict[str, object]] = []
    for name in PROCESSES:
        cases += _family_cases(name)
    return cases + _injection_cases() + _vague_cases()


def write_workflow(name: str) -> int:
    """Write `set.jsonl` for the propose-workflow set."""
    cases = workflow_cases()
    (Path(rules.EVALS) / name / "set.jsonl").write_text(
        "".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases), encoding="utf-8"
    )
    print(f"wrote {len(cases)} cases for {name}")
    return 0
