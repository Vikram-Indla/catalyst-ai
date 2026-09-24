"""Draft-only children: wording only; a candidate stating a new number is withheld and counted."""

from catalyst_ai.capabilities.generate_children.drafts import as_drafts
from catalyst_ai.capabilities.generate_children.pipeline import assemble, parse, run
from catalyst_ai.capabilities.generate_children.schema import ModelOutput
from catalyst_ai.contract.generate_children import GenerateChildrenRequest
from tests.unit.capabilities.generate_children.conftest import candidates_text, make_request
from tests.unit.capabilities.improve_story.conftest import ScriptedProvider, make_runtime

LEVELS = ["project_card", "project_objective"]
CARD = "Clear the backlog of ١٢٠٠ paper applications. Replace the paper form with the portal."


def drafts_request(**overrides: object) -> GenerateChildrenRequest:
    values: dict[str, object] = {
        "target": "children",
        "hierarchy": LEVELS,
        "parent_level": "project_card",
        "parent_title": "Permit portal",
        "parent_description": CARD,
        "draft_only": True,
        "child_focus": "One concrete result the project delivers.",
    }
    values.update(overrides)
    return make_request(**values)


def test_drafts_lose_their_criteria_and_come_back_in_latin_digits() -> None:
    output = ModelOutput.model_validate_json(
        candidates_text("Clear the backlog of ١٢٠٠ applications", level="project_objective")
    )
    kept, withheld = as_drafts(output.candidates, drafts_request())
    assert withheld == 0
    assert kept[0].title == "Clear the backlog of 1200 applications"
    assert kept[0].acceptance_criteria == []


def test_a_draft_stating_a_target_the_parent_lacks_is_withheld() -> None:
    output = ModelOutput.model_validate_json(
        candidates_text(
            "Clear the backlog of 1200 applications",
            "Cut review time to 3 days",
            level="project_objective",
        )
    )
    kept, withheld = as_drafts(output.candidates, drafts_request())
    assert [c.title for c in kept] == ["Clear the backlog of 1200 applications"]
    assert withheld == 1


def test_without_draft_only_candidates_pass_untouched() -> None:
    output = ModelOutput.model_validate_json(candidates_text("Cut review time to 3 days"))
    kept, withheld = as_drafts(output.candidates, make_request())
    assert kept == output.candidates
    assert withheld == 0


async def test_the_response_marks_drafts_and_counts_the_withheld() -> None:
    text = candidates_text(
        "Replace the paper form with the portal", "Reach 95% online use", level="project_objective"
    )
    response = await run(drafts_request(), make_runtime(ScriptedProvider([text])), "rid")
    assert [c.title for c in response.candidates] == ["Replace the paper form with the portal"]
    assert all(c.draft and not c.acceptance_criteria for c in response.candidates)
    assert response.withheld == 1


async def test_the_draft_rule_and_the_child_focus_travel_only_when_asked() -> None:
    runtime = make_runtime(ScriptedProvider([""]))
    asked = assemble(parse(drafts_request(), "rid", None), runtime)
    names = [s.name for s in asked.segments]
    assert "drafts" in names
    assert "child_focus" in names
    plain = assemble(parse(make_request(), "rid", None), runtime)
    assert {"drafts", "child_focus"}.isdisjoint(s.name for s in plain.segments)
