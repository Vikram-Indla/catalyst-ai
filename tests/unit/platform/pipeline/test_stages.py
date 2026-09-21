"""The runner calls the stages in order and serves the cache in front of the call."""

import dataclasses

from catalyst_ai.capabilities.improve_story.pipeline import STAGES, Parsed
from catalyst_ai.platform.pipeline import run_stages
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import (
    GOOD_TEXT,
    ScriptedProvider,
    make_request,
    make_runtime,
)


async def test_run_stages_end_to_end_and_cached() -> None:
    provider = ScriptedProvider([GOOD_TEXT])
    runtime = make_runtime(provider)
    first = await run_stages(STAGES, make_request(), runtime, "r1", None)
    second = await run_stages(STAGES, make_request(), runtime, "r2", None)
    assert first.changed is True
    assert second.usage.cache_hit is True
    assert len(provider.calls) == 1


async def test_run_stages_runs_the_retrieve_slot_after_the_door_and_before_assemble() -> None:
    seen: list[str] = []

    async def retrieve(parsed: Parsed, runtime: RuntimeContext) -> Parsed:
        seen.append("retrieve")
        return parsed

    stages = dataclasses.replace(STAGES, retrieve=retrieve)
    provider = ScriptedProvider([GOOD_TEXT])
    runtime = make_runtime(provider)
    await run_stages(stages, make_request(), runtime, "r1", None)
    assert seen == ["retrieve"]
    await run_stages(stages, make_request(), runtime, "r2", None)
    assert seen == ["retrieve"]
