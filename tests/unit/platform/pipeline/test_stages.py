"""The runner calls the stages in order and serves the cache in front of the call."""

from catalyst_ai.capabilities.improve_story.pipeline import STAGES
from catalyst_ai.platform.pipeline import run_stages
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
