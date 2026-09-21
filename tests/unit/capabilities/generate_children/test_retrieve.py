"""Stage 3: indexed items at the child level join the sibling pool; nothing indexed, nothing asked."""

import hashlib

from catalyst_ai.capabilities.generate_children import run
from catalyst_ai.capabilities.generate_children.retrieve import indexed_siblings
from catalyst_ai.capabilities.search import run_upsert
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.search import IndexUpsertRequest
from tests.unit.capabilities.generate_children.conftest import candidates_text, make_request
from tests.unit.capabilities.improve_story.conftest import (
    ORG,
    ScriptedProvider,
    make_runtime,
    make_settings,
)

SHARED = "Members share saved filters with a team"


def _upsert(kind: str = "story", key: str = "PRJ-7") -> IndexUpsertRequest:
    return IndexUpsertRequest.model_validate(
        {
            "organization_id": ORG,
            "capability_version": "1.0.0",
            "corpus": "work_items",
            "documents": [
                {
                    "external_id": key,
                    "kind": kind,
                    "title": SHARED,
                    "text": SHARED + " and see the shared ones in the team section.",
                    "data_class": "CONFIDENTIAL",
                    "content_hash": hashlib.sha256(SHARED.encode()).hexdigest(),
                }
            ],
        }
    )


async def test_an_indexed_child_marks_the_matching_candidate_as_duplicate() -> None:
    provider = ScriptedProvider([candidates_text(SHARED, "Unshare a filter")])
    runtime = make_runtime(provider)
    await run_upsert(_upsert(), runtime, "r0")
    response = await run(make_request(), runtime, "r1")
    assert response.index_consulted is True
    assert response.candidates[0].duplicate_of == SHARED
    assert response.candidates[1].duplicate_of is None
    assert provider.embed_calls[-1].purpose == "query"


async def test_nothing_indexed_means_no_embedding_call_and_no_consultation() -> None:
    provider = ScriptedProvider([candidates_text(SHARED)])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert response.index_consulted is False
    assert response.candidates[0].duplicate_of is None
    assert provider.embed_calls == []


async def test_only_the_child_level_and_not_the_supplied_keys() -> None:
    provider = ScriptedProvider([candidates_text(SHARED)])
    runtime = make_runtime(provider)
    await run_upsert(_upsert(kind="epic"), runtime, "r0")
    assert await indexed_siblings(make_request(), "story", runtime) == ()
    await run_upsert(_upsert(kind="story", key="PRJ-8"), runtime, "r0")
    request = make_request(siblings=[{"key": "PRJ-8", "title": "Already sent"}])
    assert await indexed_siblings(request, "story", runtime) == ()
    assert await indexed_siblings(make_request(), "story", runtime) == (SHARED,)


async def test_the_search_switch_off_skips_the_index() -> None:
    provider = ScriptedProvider([candidates_text(SHARED)])
    runtime = make_runtime(
        provider, make_settings(capability_search=CapabilitySettings(enabled=False))
    )
    await run_upsert(_upsert(), make_runtime(provider, storage=runtime.storage), "r0")
    assert await indexed_siblings(make_request(), "story", runtime) is None
