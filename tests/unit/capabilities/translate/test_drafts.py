"""The drafts job: machine drafts only, keyed per item, Latin digits, facts reported, stops honest."""

import typing
from datetime import timedelta

from catalyst_ai.capabilities.translate.drafts import item_key, run_drafts
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.translate_drafts import DraftItem, DraftsRequest
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateRequest, GenerateResult
from tests.unit.capabilities.improve_story.conftest import (
    ORG,
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tests.unit.capabilities.translate.conftest import translation_text

KR_EN = "Raise online permits from 40% to 70% by 2026-12-31 (KR-7)."
KR_AR = "رفع التصاريح الإلكترونية من ٤٠٪ إلى ٧٠٪ بحلول 2026-12-31 (KR-7)."
GLOSSARY = [{"source": "online permits", "target": "التصاريح الإلكترونية"}]


def drafts_request(*texts: str, version: str = "g1") -> DraftsRequest:
    items = [
        {"record_ref": f"kr-{index}", "field": "name", "en": text}
        for index, text in enumerate(texts)
    ]
    return DraftsRequest.model_validate(
        {
            "organization_id": ORG,
            "capability_version": "1.2.0",
            "items": items,
            "glossary": GLOSSARY,
            "glossary_version": version,
        }
    )


class ClockMover(ScriptedProvider):
    """A provider whose every call takes an hour of the runtime's clock."""

    def __init__(self, texts: list[str]) -> None:
        super().__init__(texts)
        self.runtime: typing.Any = None

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        result = await super().generate(request)
        self.runtime.clock.at += timedelta(hours=1)
        return result


class Unavailable(ScriptedProvider):
    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls.append(request)
        raise Error(ErrorCode.PROVIDER_UNAVAILABLE, "down")


def test_the_key_is_the_record_the_field_the_text_and_the_glossary_version() -> None:
    item = DraftItem(record_ref="kr-1", field="name", en="Raise permits")
    same = item_key(item, "g1")
    assert same == item_key(DraftItem(record_ref="kr-1", field="name", en="Raise permits"), "g1")
    assert same != item_key(item, "g2")
    assert same != item_key(DraftItem(record_ref="kr-1", field="name", en="Raise permit"), "g1")
    assert same != item_key(DraftItem(record_ref="kr-1", field="charter", en="Raise permits"), "g1")
    assert same != item_key(DraftItem(record_ref="kr-2", field="name", en="Raise permits"), "g1")


async def test_a_draft_is_latin_in_digits_marked_machine_and_reports_what_it_dropped() -> None:
    dropped = "رفع التصاريح الإلكترونية من ٤٠٪ بحلول 2026-12-31."
    provider = ScriptedProvider([translation_text(KR_AR), translation_text(dropped)])
    response = await run_drafts(drafts_request(KR_EN, KR_EN + " "), make_runtime(provider), "rid")
    first, second = response.drafts
    assert first.status == second.status == "machine_draft"
    assert "40٪" in first.ar
    assert not any("٠" <= ch <= "٩" for ch in first.ar)
    assert first.glossary_hits == ["online permits"]
    assert first.unresolved == []
    assert "fact_not_kept: 70" in second.unresolved
    assert "fact_not_kept: KR-7" in second.unresolved
    assert response.progress.model_dump() == {
        "total": 2,
        "drafted": 2,
        "skipped": 0,
        "remaining": 0,
        "from_cache": 0,
    }


async def test_an_empty_field_is_skipped_and_reported_without_a_call() -> None:
    provider = ScriptedProvider([translation_text(KR_AR)])
    response = await run_drafts(drafts_request("", "   ", KR_EN), make_runtime(provider), "rid")
    assert [s.reason for s in response.skipped] == ["empty", "empty"]
    assert len(response.drafts) == 1
    assert len(provider.calls) == 1


async def test_a_resubmitted_batch_drafts_only_what_changed() -> None:
    provider = ScriptedProvider(
        [translation_text(KR_AR), translation_text("يقدّم السكان إلكترونيا.")]
    )
    runtime = make_runtime(provider)
    await run_drafts(drafts_request(KR_EN, "Residents apply online."), runtime, "first")
    assert len(provider.calls) == 2
    again = await run_drafts(drafts_request(KR_EN, "Residents apply online."), runtime, "again")
    assert len(provider.calls) == 2
    assert again.progress.from_cache == 2
    assert again.usage.cost_micros == 0
    changed = await run_drafts(drafts_request(KR_EN, "Residents apply online now."), runtime, "c")
    assert len(provider.calls) == 3
    assert changed.progress.from_cache == 1
    bumped = await run_drafts(drafts_request(KR_EN, version="g2"), runtime, "g2")
    assert len(provider.calls) == 4
    assert bumped.progress.from_cache == 0


async def test_the_budget_stops_the_run_and_the_rest_is_remaining() -> None:
    provider = ScriptedProvider([translation_text(KR_AR)])
    runtime = make_runtime(provider, make_settings(tenant_budget_default_micros_per_day=1_000))
    response = await run_drafts(drafts_request(*[KR_EN + str(n) for n in range(6)]), runtime, "b")
    assert response.progress.drafted >= 1
    assert response.progress.remaining >= 1
    assert {r.reason for r in response.remaining} == {"budget_exhausted"}
    assert response.progress.drafted + response.progress.remaining == 6
    assert len(provider.calls) == response.progress.drafted


async def test_an_unavailable_provider_leaves_every_item_remaining() -> None:
    provider = Unavailable([""])
    response = await run_drafts(drafts_request(KR_EN, KR_EN + "!"), make_runtime(provider), "u")
    assert [r.reason for r in response.remaining] == ["provider_unavailable"] * 2
    assert len(provider.calls) == 1
    assert response.model.endswith("@none")


async def test_the_jobs_time_stops_the_run_before_its_deadline() -> None:
    provider = ClockMover([translation_text(KR_AR)])
    runtime = make_runtime(provider, make_settings(job_timeout_seconds=3_600))
    provider.runtime = runtime
    response = await run_drafts(drafts_request(KR_EN, KR_EN + "!", KR_EN + "?"), runtime, "t")
    assert response.progress.drafted == 1
    assert [r.reason for r in response.remaining] == ["time_exhausted"] * 2


async def test_a_refused_item_is_skipped_with_its_code_and_the_run_goes_on() -> None:
    provider = ScriptedProvider(["not json", "still not json", translation_text(KR_AR)])
    response = await run_drafts(drafts_request(KR_EN, KR_EN + "!"), make_runtime(provider), "r")
    assert [(s.reason, s.code) for s in response.skipped] == [("refused", "ai.output.invalid")]
    assert len(response.drafts) == 1
