"""Deterministic graders for improve-story: each scores one property of a response in [0, 1]."""

import re
from collections.abc import Callable

from catalyst_ai.capabilities.improve_story.quality import (
    dominant_script,
    has_given_when_then,
    identifiers,
    length_ratio,
    script_preserved,
)
from catalyst_ai.contract.improve_story import ImproveStoryRequest, ImproveStoryResponse
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
    ratio = length_ratio(request.description, response.improved_description)
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
    if not request.description.strip():
        return 1.0
    return _score(script_preserved(request.description, response.improved_description))


def identifiers_kept(
    request: ImproveStoryRequest, response: ImproveStoryResponse, expected: dict[str, object]
) -> float:
    """Every key and number of the source survives, except the ones the case forbids."""
    result = response.improved_description + "\n" + (response.acceptance_criteria or "")
    forbidden = set(_terms(expected))
    required = identifiers(request.description) - forbidden
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
        )
        if t
    ]
    if scan_output(result, texts):
        return 0.0
    terms = _terms(expected)
    changed = response.improved_description.strip() != request.description.strip()
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
        checks.append(response.improved_description.strip() == request.description.strip())
    return _score(all(checks)) if checks else 1.0


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "length_bounds": length_bounds,
    "language_preserved": language_preserved,
    "identifiers_kept": identifiers_kept,
    "no_forbidden_content": no_forbidden_content,
    "rationale_present": rationale_present,
    "mode_shape": mode_shape,
}
