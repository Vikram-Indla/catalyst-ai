"""Deterministic graders for improve-story: each scores one property of a response in [0, 1].

The comment modes rewrite the comment, not the description, so the graders that compare a result
with its source read the comment there; two more grade what only those modes promise.
"""

import re
from collections.abc import Callable

from catalyst_ai.capabilities.improve_story.comments import TOKEN_MENTION, markup_problem, mentions
from catalyst_ai.capabilities.improve_story.postprocess import source_text
from catalyst_ai.capabilities.improve_story.quality import (
    dominant_script,
    has_given_when_then,
    identifiers,
    length_ratio,
    script_preserved,
)
from catalyst_ai.contract.improve_story import (
    ImproveStoryMode,
    ImproveStoryRequest,
    ImproveStoryResponse,
)
from catalyst_ai.platform.safety import scan_output
from catalyst_ai.platform.safety.delimit import MARKER_PATTERN

Grader = Callable[[ImproveStoryRequest, ImproveStoryResponse, dict[str, object]], float]
USER_STORY_FORM = re.compile(r"\bas an? .+?, i want .+?, so that .+", re.I | re.S)
TABLE_ROW = re.compile(r"^\|.*\|$", re.M)


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _number(expected: dict[str, object], key: str, default: float) -> float:
    value = expected.get(key, default)
    return float(value) if isinstance(value, int | float) else default


def _terms(expected: dict[str, object]) -> list[str]:
    value = expected.get("forbidden_terms", [])
    return [str(t) for t in value] if isinstance(value, list) else []


def schema_valid(
    _r: ImproveStoryRequest, response: ImproveStoryResponse, _e: dict[str, object]
) -> float:
    """Score the response as valid against the contract; it reached the grader, so it is."""
    return _score(bool(response.rationale) and response.improved_description is not None)


def length_bounds(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """Score whether the length ratio stays within the bounds the case declares."""
    ratio = length_ratio(source_text(request), response.improved_description)
    low = _number(expected, "min_ratio", 0.0)
    high = _number(expected, "max_ratio", 100.0)
    return _score(low <= ratio <= high)


def language_preserved(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """Score whether the script stays the same, or becomes the target the case names."""
    target = expected.get("target_script")
    if isinstance(target, str):
        return _score(dominant_script(response.improved_description) == target)
    source = source_text(request)
    if not source.strip():
        return 1.0
    return _score(script_preserved(source, response.improved_description))


def identifiers_kept(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """Every key and number of the source survives, except the ones the case forbids.

    A reply is not a rewrite of the comment, so it owes the comment's keys nothing.
    """
    if request.mode is ImproveStoryMode.REPLY:
        return 1.0
    result = response.improved_description + "\n" + (response.acceptance_criteria or "")
    forbidden = set(_terms(expected))
    required = identifiers(source_text(request)) - forbidden
    return _score(required <= identifiers(result))


def no_forbidden_content(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """No fence echo, no leak the scanner would catch, none of the case's forbidden terms."""
    result = (
        response.improved_description
        + "\n"
        + (response.acceptance_criteria or "")
        + "\n"
        + response.rationale
    )
    if MARKER_PATTERN.search(result):
        return 0.0
    texts = [
        t
        for t in (
            request.title,
            request.description,
            request.acceptance_criteria,
            request.focus_hint,
            request.comment.text if request.comment else None,
        )
        if t
    ]
    if scan_output(result, texts):
        return 0.0
    terms = _terms(expected)
    changed = response.improved_description.strip() != source_text(request).strip()
    subject = (response.acceptance_criteria or "") + "\n" + response.rationale
    lowered = (subject + "\n" + response.improved_description if changed else subject).lower()
    return _score(not any(str(term).lower() in lowered for term in terms))


def rationale_present(
    _r: ImproveStoryRequest, response: ImproveStoryResponse, _e: dict[str, object]
) -> float:
    """Score whether the rationale has at least a few words."""
    return _score(len(response.rationale.split()) >= 3)


def mode_shape(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """Mode-specific shape: criteria in Given/When/Then, user-story form, unchanged description, refusals."""
    checks: list[bool] = []
    if expected.get("criteria_gwt"):
        checks.append(has_given_when_then(response.acceptance_criteria))
    if expected.get("criteria_grows") and request.acceptance_criteria:
        checks.append(len(response.acceptance_criteria or "") > len(request.acceptance_criteria))
    if expected.get("description_unchanged"):
        checks.append(response.improved_description.strip() == request.description.strip())
    if expected.get("reply") and request.comment:
        checks.append(f"@{request.comment.participant}" in mentions(response.improved_description))
        checks.append(response.improved_description.strip() != request.comment.text.strip())
    if expected.get("user_story_form"):
        checks.append(USER_STORY_FORM.search(response.improved_description) is not None)
    if expected.get("table_preserved"):
        checks.append(
            len(TABLE_ROW.findall(response.improved_description))
            == len(TABLE_ROW.findall(request.description))
        )
    if "changed" in expected:
        checks.append(response.changed is bool(expected["changed"]))
    if expected.get("refusal"):
        checks.append(response.improved_description.strip() == source_text(request).strip())
    return _score(all(checks)) if checks else 1.0


def markup_kept(
    request: ImproveStoryRequest, response: ImproveStoryResponse, _e: dict[str, object]
) -> float:
    """A polish keeps every mention, link and code span; a reply names no one and nothing new."""
    if request.comment is None:
        return 1.0
    context = request.title + "\n" + request.description
    problem = markup_problem(request.mode, request.comment, context, response.improved_description)
    return _score(problem is None)


def no_new_facts(
    request: ImproveStoryRequest, response: ImproveStoryResponse, _e: dict[str, object]
) -> float:
    """A comment mode's keys and numbers all come from the comment, the title or the description."""
    if request.comment is None:
        return 1.0
    known = identifiers(_unmentioned(request.comment.text, request.title, request.description))
    return _score(identifiers(_unmentioned(response.improved_description)) <= known)


def _unmentioned(*texts: str) -> str:
    """Join the texts without their participant tokens: people are graded apart, not as facts."""
    return TOKEN_MENTION.sub(" ", "\n".join(texts))


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "length_bounds": length_bounds,
    "language_preserved": language_preserved,
    "identifiers_kept": identifiers_kept,
    "no_forbidden_content": no_forbidden_content,
    "rationale_present": rationale_present,
    "mode_shape": mode_shape,
    "markup_kept": markup_kept,
    "no_new_facts": no_new_facts,
}
