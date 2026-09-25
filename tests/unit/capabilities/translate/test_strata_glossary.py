"""A whole strategy vocabulary through translate and the drafts job: settled terms enforced
exactly, every term with two renderings reported as ambiguous, whichever one the draft chose."""

from catalyst_ai.capabilities.translate import run
from catalyst_ai.capabilities.translate.drafts import run_drafts
from catalyst_ai.contract.translate import MAX_GLOSSARY
from catalyst_ai.contract.translate_drafts import DraftsRequest
from tests.unit.capabilities.improve_story.conftest import ORG, ScriptedProvider, make_runtime
from tests.unit.capabilities.translate.conftest import make_request, translation_text
from tests.unit.capabilities.translate.strata_glossary import (
    FLAGGED,
    SETTLED,
    TERMS,
    Term,
    glossary,
    rendering,
    sentence,
)

AMBIGUOUS = "ambiguous_glossary"
NOT_RENDERED = "term_not_rendered"
MODULE_SENTENCES = (
    (
        "Each Project Card hangs from one Theme, and its Project Objective aligns to one OKR.",
        "كل بطاقة المشروع تتبع المحور الاستراتيجي، ويتسق هدف المشروع مع الأهداف والنتائج"
        " الرئيسية (OKR).",
    ),
    (
        "A Direct Component binds a Project KPI to one Strategic KPI.",
        "يربط المكوّن المباشر مؤشر أداء المشروع بمؤشر الأداء الاستراتيجي.",
    ),
    (
        "The Key Result is At risk: its Actual is below the Baseline.",
        "النتيجة الرئيسية معرّض للخطر: القيمة الفعلية أدنى من خط الأساس.",
    ),
    (
        "A Legal hold stops the Disposition proof until the STRATA Admin releases it.",
        "يوقف التحفظ القانوني إثبات الإتلاف حتى يرفعه مسؤول STRATA.",
    ),
)


def names(term_list: tuple[Term, ...]) -> list[str]:
    return [term.source for term in term_list]


async def translated(text: str, arabic: str) -> tuple[list[str], list[tuple[str, str]]]:
    request = make_request(text=text, source_language="en", glossary=glossary())
    response = await run(request, make_runtime(ScriptedProvider([translation_text(arabic)])), "r")
    conflicts = [(conflict.source, str(conflict.reason)) for conflict in response.glossary_conflict]
    return response.glossary_applied, conflicts


def test_the_fixture_is_one_request_glossary_with_each_source_listed_once_per_rendering() -> None:
    assert len(TERMS) == 67
    assert len(FLAGGED) == 31
    assert len({term.source.casefold() for term in TERMS}) == len(TERMS)
    assert len(glossary()) == len(TERMS) + len(FLAGGED) <= MAX_GLOSSARY


async def test_every_settled_term_is_enforced_exactly_in_its_sentence() -> None:
    for term in SETTLED:
        assert await translated(sentence(term), rendering(term)) == ([term.source], [])
        assert await translated(sentence(term), rendering(term, "كلمة أخرى")) == (
            [],
            [(term.source, NOT_RENDERED)],
        )


async def test_every_flagged_term_is_reported_whichever_rendering_the_draft_chose() -> None:
    for term in FLAGGED:
        for chosen in (term.target, term.alternative):
            assert await translated(sentence(term), rendering(term, chosen)) == (
                [],
                [(term.source, AMBIGUOUS)],
            )


async def test_the_modules_own_sentences_enforce_each_term_once_and_no_term_inside_another() -> (
    None
):
    applied = []
    for text, arabic in MODULE_SENTENCES:
        found, conflicts = await translated(text, arabic)
        assert all(reason == AMBIGUOUS for _, reason in conflicts), (text, conflicts)
        applied.append(found)
    assert applied == [
        ["Project Card", "Project Objective"],
        ["Strategic KPI", "Project KPI"],
        ["Key Result", "Baseline", "Actual", "At risk"],
        ["Disposition proof", "STRATA Admin"],
    ]


async def test_the_drafts_job_drafts_every_term_reporting_the_flagged_to_the_reviewer() -> None:
    items = [
        {"record_ref": f"rec-{index}", "field": "name", "en": sentence(term)}
        for index, term in enumerate(TERMS)
    ]
    request = DraftsRequest.model_validate(
        {
            "organization_id": ORG,
            "capability_version": "1.2.0",
            "items": items,
            "glossary": glossary(),
            "glossary_version": "fixture-1",
        }
    )
    provider = ScriptedProvider([translation_text(rendering(term)) for term in TERMS])
    response = await run_drafts(request, make_runtime(provider), "rid")
    assert [draft.status for draft in response.drafts] == ["machine_draft"] * len(TERMS)
    by_source = dict(zip(names(TERMS), response.drafts, strict=True))
    for term in SETTLED:
        assert by_source[term.source].glossary_hits == [term.source]
        assert by_source[term.source].unresolved == []
    for term in FLAGGED:
        assert by_source[term.source].glossary_hits == []
        assert by_source[term.source].unresolved == [f"{AMBIGUOUS}: {term.source}"]
