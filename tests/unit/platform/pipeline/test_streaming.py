"""The streaming runner: visible deltas only, one usage, one done; the tail never leaks."""

import dataclasses
from collections.abc import Callable

import pytest

from catalyst_ai.capabilities.improve_story.pipeline import STAGES, Parsed
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.improve_story import ImproveStoryResponse
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Event, hold_back, run_streaming
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    STREAM_FAULT,
    ScriptedProvider,
    make_request,
    make_runtime,
)

MARKER = "\n---\n"


def test_hold_back_keeps_a_split_marker_out_of_sight() -> None:
    assert hold_back("plain prose", MARKER) == "plain prose"
    assert hold_back("prose\n", MARKER) == "prose"
    assert hold_back("prose\n--", MARKER) == "prose"
    assert hold_back("prose\n---\n{tail}", MARKER) == "prose"
    assert hold_back("a - b", MARKER) == "a - b"
    assert hold_back("", MARKER) == ""


async def _events(
    runtime: RuntimeContext, visible: Callable[[str], str] = str
) -> list[Event[ImproveStoryResponse]]:
    return [event async for event in run_streaming(STAGES, make_request(), runtime, "r1", visible)]


async def test_deltas_join_to_the_completion_and_the_response_is_validated() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    events = await _events(make_runtime(provider))
    kinds = [event.kind for event in events]
    assert kinds[-2:] == ["usage", "done"]
    assert kinds.count("usage") == 1
    assert "".join(event.text for event in events if event.kind == "delta") == GOOD_TEXT
    assert events[-1].result is not None
    assert events[-2].usage is not None
    assert len(provider.calls) == 1


async def test_only_the_visible_prefix_streams() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    shown = await _events(make_runtime(provider), lambda text: text[:10])
    assert "".join(e.text for e in shown if e.kind == "delta") == GOOD_TEXT[:10]
    assert shown[-1].kind == "done"


async def test_a_settled_run_yields_done_without_a_call() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    runtime = make_runtime(provider)
    first = [e async for e in run_streaming(STAGES, make_request(), runtime, "r0", str)]
    settled = first[-1].result
    assert settled is not None

    def settle(parsed: Parsed, runtime: RuntimeContext) -> ImproveStoryResponse | None:
        del parsed, runtime
        return settled

    stages = dataclasses.replace(STAGES, settle=settle)
    events = [e async for e in run_streaming(stages, make_request(), runtime, "r1", str)]
    assert [e.kind for e in events] == ["done"]
    assert events[0].result is settled
    assert len(provider.calls) == 1


async def test_a_broken_stream_raises_the_catalog_error_after_no_terminal_event() -> None:
    provider = ScriptedProvider([STREAM_FAULT])
    with pytest.raises(Error) as caught:
        await _events(make_runtime(provider))
    assert caught.value.code is ErrorCode.PROVIDER_UNAVAILABLE
