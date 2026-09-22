"""The documents job path: the size line and the runner over a stored payload."""

import base64

import pytest

from catalyst_ai.capabilities.documents.jobs import (
    SYNC_MAX_BYTES,
    document_bytes,
    refuse_above_the_line,
    run_ingest_payload,
)
from catalyst_ai.contract.documents import IngestResponse
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.documents.conftest import ingest_request, sha
from tests.unit.capabilities.improve_story.conftest import ScriptedProvider, make_runtime


def test_the_size_line_counts_decoded_bytes_and_refuses_above_it() -> None:
    small = ingest_request()
    assert document_bytes(small) == len(small.text or "")
    refuse_above_the_line(small)
    big = "x" * (SYNC_MAX_BYTES + 100)
    encoded = base64.b64encode(big.encode()).decode()
    large = ingest_request(text=None, content_base64=encoded, content_hash=sha(big))
    assert document_bytes(large) > SYNC_MAX_BYTES
    with pytest.raises(Error) as raised:
        refuse_above_the_line(large)
    assert raised.value.code is ErrorCode.INPUT_TOO_LARGE
    assert raised.value.details[0].code == "use_the_job_operation"


async def test_the_runner_parses_the_stored_payload_and_refuses_what_is_not_the_request() -> None:
    runtime = make_runtime(ScriptedProvider([]))
    payload = ingest_request().model_dump_json().encode()
    result = await run_ingest_payload(payload, runtime, "job-1")
    assert isinstance(result, IngestResponse)
    assert result.state == "indexed"
    with pytest.raises(Error) as raised:
        await run_ingest_payload(b"not the request", runtime, "job-2")
    assert raised.value.code is ErrorCode.VALIDATION_INVALID_INPUT
