"""The window modes: the door, the window cut, the two shapes, the count echo, the lines."""

import pytest

from catalyst_ai.capabilities.summarize.modes import (
    clean_lines,
    counts_text,
    digest_groups,
    lines_of,
    require_window,
    standup_entries,
    window_text,
    within_window,
)
from catalyst_ai.capabilities.summarize.schema import ModelOutput
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.summarize import MAX_LINE_CHARS, MAX_LINES
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.summarize.conftest import item, make_request

WINDOW = {"from_at": "2026-09-01T00:00:00+00:00", "to_at": "2026-09-01T23:59:00+00:00"}
OUTSIDE = "2026-09-03T09:00:00+00:00"
COUNTS = [{"kind": "work_item", "count": 17}, {"kind": "release", "count": 0}]


def _items() -> list[dict[str, object]]:
    inside = [
        {**item(1, "Done: merged PRJ-1.", "p2"), "kind": "work_item"},
        {**item(2, "Blocked: waiting on ops.", "p1"), "kind": "work_item"},
    ]
    outside = {**item(3, "Done: PRJ-9 shipped.", "p3"), "at": OUTSIDE, "kind": "release"}
    return [*inside, outside]


def test_require_window_names_the_missing_piece() -> None:
    require_window(make_request())
    with pytest.raises(Error) as no_window:
        require_window(make_request(mode="standup"))
    assert no_window.value.code is ErrorCode.INPUT_REJECTED
    assert no_window.value.details[0].code == "window_required"
    with pytest.raises(Error) as no_counts:
        require_window(make_request(mode="digest", window=WINDOW))
    assert no_counts.value.details[0].code == "counts_required"
    require_window(make_request(mode="digest", window=WINDOW, counts=COUNTS))


def test_within_window_keeps_only_what_the_span_covers() -> None:
    request = make_request(mode="standup", items=_items(), window=WINDOW)
    cut = within_window(request)
    assert [i.id for i in cut.items] == ["c1", "c2"]
    assert within_window(make_request()).items == make_request().items
    assert window_text(request) == "2026-09-01T00:00:00+00:00 to 2026-09-01T23:59:00+00:00"
    assert window_text(make_request()) == ""
    assert counts_text(make_request(counts=COUNTS)) == "work_item: 17\nrelease: 0"


def test_standup_entries_follow_the_tokens_of_the_items() -> None:
    request = within_window(make_request(mode="standup", items=_items(), window=WINDOW))
    output = ModelOutput.model_validate(
        {
            "summary": "p1 blocked.",
            "participants_mentioned": ["p1"],
            "rationale": "r",
            "standup": [
                {"participant": "p1", "done": [], "doing": [], "blocked": ["- waiting on ops "]},
                {"participant": "p7", "done": ["x"], "doing": [], "blocked": []},
            ],
        }
    )
    entries = standup_entries(output, request)
    assert [e.participant for e in entries] == ["p1", "p2"]
    assert entries[0].blocked == ["waiting on ops"]
    assert entries[1].done == []
    assert standup_entries(output, make_request()) == []
    assert digest_groups(output, request) == []


def test_digest_groups_echo_the_request_counts_in_order() -> None:
    request = make_request(mode="digest", items=_items(), window=WINDOW, counts=COUNTS)
    output = ModelOutput.model_validate(
        {
            "summary": "s",
            "participants_mentioned": [],
            "rationale": "r",
            "digest": [
                {"kind": "release", "changes": ["2.4 tagged"]},
                {"kind": "unknown", "changes": ["dropped"]},
                {"kind": "work_item", "changes": ["PRJ-1 merged", "", "p1 blocked"]},
            ],
        }
    )
    groups = digest_groups(output, request)
    assert [(g.kind, g.count) for g in groups] == [("work_item", 17), ("release", 0)]
    assert groups[0].changes == ["PRJ-1 merged", "p1 blocked"]
    assert groups[1].changes == ["2.4 tagged"]
    assert lines_of([], groups) == "PRJ-1 merged\np1 blocked\n2.4 tagged"


def test_clean_lines_caps_count_and_length() -> None:
    lines = clean_lines(["• " + "x" * 400, *["y"] * 20])
    assert len(lines) == MAX_LINES
    assert len(lines[0]) == MAX_LINE_CHARS
    assert lines[0].endswith("…")
