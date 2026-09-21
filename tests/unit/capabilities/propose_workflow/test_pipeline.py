"""The propose-workflow pipeline over the scripted provider: the data, the door, the cache."""

import pytest

from catalyst_ai.capabilities.propose_workflow import descriptor, run
from catalyst_ai.capabilities.propose_workflow.pipeline import assemble, parse, scheme_text
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.propose_workflow import Scheme
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.propose_workflow.conftest import (
    STATUSES,
    TRANSITIONS,
    make_request,
    proposal_text,
)


async def test_run_returns_the_scheme_with_versions_and_caches_it() -> None:
    provider = ScriptedProvider([proposal_text()])
    runtime = make_runtime(provider)
    response = await run(make_request(), runtime, "r1")
    assert [s.key for s in response.statuses][:2] == ["reported", "triaged"]
    assert response.transitions[-1].kind.value == "cancel"
    assert response.empty_reason is None
    assert response.capability_version == descriptor.version
    assert response.model.endswith("@double")
    again = await run(make_request(), runtime, "r2")
    assert again.usage.cache_hit is True
    assert len(provider.calls) == 1


def test_scheme_text_is_one_line_per_status_and_transition() -> None:
    scheme = Scheme.model_validate({"statuses": STATUSES, "transitions": TRANSITIONS})
    lines = scheme_text(scheme).splitlines()
    assert lines[0] == "status reported [todo] name='Reported' initial"
    assert lines[4] == "status closed [done] name='Closed' terminal"
    assert lines[7] == "transition triaged -> in_work (forward) guards=assignee_set"
    assert lines[8] == "transition in_work -> triaged (backward) reason=needs_triage"
    assert lines[-1] == "transition * -> cancelled (cancel)"
    assert scheme_text(None) == ""


def test_assemble_fences_the_description_and_names_the_vocabulary() -> None:
    existing = {"statuses": STATUSES[:1], "transitions": []}
    parsed = parse(make_request(existing=existing, language="ar"), "rid", None)
    generate = assemble(parsed, make_runtime(ScriptedProvider([proposal_text()])))
    developer = generate.segments[1].text
    assert "Allowed categories: todo, in_progress, done" in developer
    assert "Guard vocabulary: assignee_set, fix_version_set, all_subtasks_done" in developer
    assert "Language of labels and rationales: ar" in developer
    assert "<<<item_type>>>\ndefect\n<<<end item_type>>>" in developer
    assert generate.segments[2].text.startswith("<<<description>>>")
    assert "status reported [todo]" in generate.segments[3].text
    assert generate.output_schema is not None
    assert generate.alias.value == descriptor.alias
    bare = assemble(
        parse(make_request(guard_vocabulary=[]), "rid", None),
        make_runtime(ScriptedProvider([proposal_text()])),
    )
    assert "Guard vocabulary: (none)" in bare.segments[1].text
    assert "<<<existing>>>\n(none)" in bare.segments[3].text


async def test_the_door_refuses_switch_scanner_and_version() -> None:
    off = make_runtime(
        ScriptedProvider([proposal_text()]),
        make_settings(capability_propose_workflow=CapabilitySettings(enabled=False)),
    )
    with pytest.raises(Error) as disabled:
        await run(make_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    runtime = make_runtime(ScriptedProvider([proposal_text()]))
    with pytest.raises(Error) as scanned:
        await run(make_request(description="mail someone@example.com when done"), runtime, "r")
    assert scanned.value.code is ErrorCode.INPUT_REJECTED
    with pytest.raises(Error) as version:
        await run(make_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH


async def test_a_label_carrying_a_foreign_link_is_unsafe() -> None:
    statuses = [{**STATUSES[0], "name": "See https://evil.example/steps"}, *STATUSES[1:]]
    provider = ScriptedProvider([proposal_text(statuses)])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "r")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE


async def test_a_malformed_scheme_is_output_invalid_with_the_detail() -> None:
    statuses = [{**s, "initial": False} for s in STATUSES]
    provider = ScriptedProvider([proposal_text(statuses)])
    with pytest.raises(Error) as caught:
        await run(make_request(), make_runtime(provider), "r")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "workflow_no_initial"
