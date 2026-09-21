"""The search pipeline: the door, retrieval through the seam, the response with its versions."""

import pytest

from catalyst_ai.capabilities.search import descriptor, run, run_upsert
from catalyst_ai.capabilities.search.pipeline import parse, timeout_ms, validate
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    OTHER_ORG,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.search.conftest import search_request, upsert_request


async def test_run_finds_an_indexed_item_and_carries_the_versions() -> None:
    provider = ScriptedProvider(["{}"])
    runtime = make_runtime(provider)
    await run_upsert(upsert_request(), runtime, "r0")
    response = await run(search_request("login button broken"), runtime, "r1")
    assert response.hits[0].external_id == "A-1"
    assert response.hits[0].title == "Login broken"
    assert response.capability_version == descriptor.version
    assert response.prompt_version == "0"
    assert response.model == f"{descriptor.alias}@double"
    assert response.embedding_version == "d768-r1"
    assert response.fusion.startswith("rrf")
    assert response.request_id == "r1"
    assert response.usage.cost_micros > 0


async def test_run_on_an_empty_organisation_costs_nothing() -> None:
    provider = ScriptedProvider(["{}"])
    runtime = make_runtime(provider)
    await run_upsert(upsert_request(), runtime, "r0")
    response = await run(search_request(organization_id=OTHER_ORG), runtime, "r1")
    assert response.hits == []
    assert response.usage.cost_micros == 0
    assert len(provider.embed_calls) == 1


def test_parse_and_the_door() -> None:
    parsed = parse(search_request("hello"), "rid")
    assert parsed.user_texts == {"text": "hello"}
    runtime = make_runtime(ScriptedProvider(["{}"]))
    assert validate(parsed, runtime)
    off = make_runtime(
        ScriptedProvider(["{}"]),
        make_settings(capability_search=CapabilitySettings(enabled=False, timeout_ms=7)),
    )
    with pytest.raises(Error) as caught:
        validate(parsed, off)
    assert caught.value.code is ErrorCode.CAPABILITY_DISABLED
    assert timeout_ms(off) == 7
    assert timeout_ms(runtime) == descriptor.timeout_ms
    with pytest.raises(Error) as scanned:
        validate(parse(search_request("mail me at someone@example.com"), "r"), runtime)
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
