"""The development stand-in walked through the real pipelines: a marked proposal, a withheld one,
draft children with one withheld, a marked summary, deterministic vectors, every other call refused."""

from uuid import UUID

import pytest

from catalyst_ai.capabilities.brief.pipeline import run as run_brief
from catalyst_ai.capabilities.generate_children.pipeline import run as run_children
from catalyst_ai.capabilities.improve_story import run as run_improve
from catalyst_ai.capabilities.summarize import run as run_summary
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.models import ModelAlias
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryStorage
from catalyst_ai.providers.port import EmbedRequest, GenerateRequest, Segment
from catalyst_ai.providers.standin import DIMENSIONS, MARK, MODEL_ID, StandInProvider
from tests.unit.capabilities.brief.conftest import brief_request
from tests.unit.capabilities.generate_children.test_drafts import drafts_request
from tests.unit.capabilities.improve_story.conftest import FrozenClock, make_settings
from tests.unit.capabilities.improve_story.test_governed import record_request
from tests.unit.capabilities.summarize.conftest import make_request as summary_request

ORG = UUID("11111111-1111-7111-8111-111111111111")


def runtime() -> RuntimeContext:
    settings, clock = make_settings(), FrozenClock()
    return RuntimeContext(
        settings=settings,
        provider=StandInProvider(),
        cache=MemoryCache(clock),
        budgets=TenantBudgets(
            clock, settings.tenant_budget_default_micros_per_day, settings.tenant_concurrency_max
        ),
        clock=clock,
        storage=MemoryStorage(clock),
    )


async def test_improve_returns_the_text_as_written_marked_as_a_stand_in() -> None:
    response = await run_improve(record_request(focus_hint=None), runtime(), "rid")
    assert response.improved_description.startswith(MARK)
    assert "from 40" in response.improved_description
    assert "to 70" in response.improved_description
    assert response.changed is True


async def test_a_hint_that_names_a_number_shows_the_withheld_refusal() -> None:
    with pytest.raises(Error) as refused:
        await run_improve(record_request(focus_hint="set a 90% stretch target"), runtime(), "rid")
    assert refused.value.code is ErrorCode.OUTPUT_INVALID
    assert [d.message for d in refused.value.details] == ["fact_added: 90"]


async def test_draft_children_come_back_marked_and_the_one_with_a_figure_is_withheld() -> None:
    response = await run_children(drafts_request(), runtime(), "rid")
    assert [c.title for c in response.candidates] == [f"{MARK} first draft", f"{MARK} second draft"]
    assert {c.type for c in response.candidates} == {"project_objective"}
    assert response.withheld == 1


async def test_the_summary_is_one_marked_line_naming_nobody() -> None:
    response = await run_summary(summary_request(), runtime(), "rid")
    assert response.summary.startswith(MARK)
    assert response.participants_mentioned == []


async def test_vectors_are_deterministic_unit_vectors_of_the_index_dimension() -> None:
    request = EmbedRequest(
        organization_id=ORG,
        capability="search",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=["one", "two", "one"],
        timeout_ms=1_000,
    )
    result = await StandInProvider().embed(request)
    first, second, again = result.vectors
    assert len(first) == DIMENSIONS
    assert first == again
    assert first != second
    assert abs(sum(v * v for v in first) - 1.0) < 1e-9
    assert result.model_id == MODEL_ID


async def test_any_other_operation_is_unavailable_and_costs_nothing() -> None:
    provider = StandInProvider()
    request = GenerateRequest(
        organization_id=ORG,
        request_id="rid",
        capability="release-notes",
        alias=ModelAlias.TEXT_DEFAULT,
        segments=[Segment(role="system", name="system", text="x")],
        temperature=0.2,
        max_output_tokens=10,
        timeout_ms=1_000,
    )
    with pytest.raises(Error) as refused:
        await provider.generate(request)
    assert refused.value.code is ErrorCode.PROVIDER_UNAVAILABLE
    assert await provider.credentials_ready() is True
    assert provider.model_id(ModelAlias.TEXT_DEFAULT) == MODEL_ID
    assert provider.count_tokens(ModelAlias.TEXT_DEFAULT, "abcdefgh") == 2
    frames = [frame async for frame in provider.stream(request)]
    assert [frame.kind for frame in frames] == ["error"]


async def test_a_charter_keeps_its_sections_with_the_mark_inside_the_first() -> None:
    charter = "## Hypothesis\n\nPermits online.\n\n## Scope\n\nResidents.\n\n## Value thesis\n\nFewer visits."
    request = record_request(item_type="theme_charter", description=charter, focus_hint=None)
    proposal = (await run_improve(request, runtime(), "rid")).improved_description
    assert proposal.startswith("## Hypothesis\n\n" + MARK)
    headings = [line for line in proposal.splitlines() if line.startswith("## ")]
    assert headings == ["## Hypothesis", "## Scope", "## Value thesis"]


async def test_the_briefing_cites_only_the_chains_ids_and_says_what_it_cannot_support() -> None:
    response = await run_brief(brief_request(), runtime(), "rid")
    sentences = [*response.summary, *response.highlights, *response.risks]
    assert len(response.summary) == 3
    assert all(sentence.text.startswith(MARK) for sentence in sentences)
    assert {cite for sentence in sentences for cite in sentence.cites} <= {"T-1", "O-1", "P-1"}
    assert response.unsupported != []
    assert response.empty_reason is None
