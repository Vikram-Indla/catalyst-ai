"""The drafts job's submission door and its runner over a stored payload."""

import pytest

from catalyst_ai.capabilities.translate.jobs import admit_drafts, run_drafts_payload
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import ScriptedProvider, make_runtime
from tests.unit.capabilities.translate.conftest import translation_text
from tests.unit.capabilities.translate.test_drafts import KR_AR, KR_EN, drafts_request


async def test_the_door_scans_every_item_before_anything_is_stored() -> None:
    runtime = make_runtime(ScriptedProvider([""]))
    admit_drafts(drafts_request(KR_EN), runtime)
    restricted = "Write to owner@example.org for the target."
    with pytest.raises(Error) as raised:
        admit_drafts(drafts_request(KR_EN, restricted), runtime)
    assert raised.value.code is ErrorCode.INPUT_REJECTED


async def test_the_runner_reads_the_stored_payload_as_the_request_or_refuses() -> None:
    runtime = make_runtime(ScriptedProvider([translation_text(KR_AR)]))
    payload = drafts_request(KR_EN).model_dump_json().encode()
    result = await run_drafts_payload(payload, runtime, "job-1")
    assert result.drafts[0].status == "machine_draft"
    with pytest.raises(Error) as raised:
        await run_drafts_payload(b"not the request", runtime, "job-2")
    assert raised.value.code is ErrorCode.VALIDATION_INVALID_INPUT
