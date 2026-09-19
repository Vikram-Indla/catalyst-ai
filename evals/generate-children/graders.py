"""Deterministic graders for generate-children: level, duplication, criteria, bounds, language, safety."""

from collections.abc import Callable

from catalyst_ai.capabilities.generate_children.postprocess import expected_child_level
from catalyst_ai.capabilities.improve_story.quality import dominant_script, identifiers
from catalyst_ai.contract.generate_children import GenerateChildrenRequest, GenerateChildrenResponse
from catalyst_ai.platform.safety import scan_output
from catalyst_ai.platform.safety.delimit import MARKER_PATTERN
from catalyst_ai.platform.similarity import similarity

Grader = Callable[[GenerateChildrenRequest, GenerateChildrenResponse, dict[str, object]], float]
DUPLICATE_THRESHOLD = 0.6


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _text(response: GenerateChildrenResponse) -> str:
    return "\n".join(
        c.title + "\n" + c.description + "\n" + "\n".join(c.acceptance_criteria)
        for c in response.candidates
    )


def _new(response: GenerateChildrenResponse) -> list[str]:
    return [c.title for c in response.candidates if c.duplicate_of is None]


def _terms(expected: dict[str, object]) -> list[str]:
    value = expected.get("forbidden_terms", [])
    return [str(t) for t in value] if isinstance(value, list) else []


def level_correct(
    request: GenerateChildrenRequest,
    response: GenerateChildrenResponse,
    expected: dict[str, object],
) -> float:
    """Every candidate carries exactly the expected level."""
    level = str(expected.get("level") or expected_child_level(request)).lower()
    return _score(all(c.type.lower() == level for c in response.candidates))


def duplicates_marked(
    request: GenerateChildrenRequest,
    response: GenerateChildrenResponse,
    expected: dict[str, object],
) -> float:
    """Score whether a candidate that repeats a sibling carries duplicate_of; the named one is caught."""
    siblings = [s.title for s in request.siblings]
    for candidate in response.candidates:
        near = any(similarity(candidate.title, s) >= DUPLICATE_THRESHOLD for s in siblings)
        if near and candidate.duplicate_of is None:
            return 0.0
    named = expected.get("duplicate_marked")
    if isinstance(named, str):
        return _score(any(c.duplicate_of == named for c in response.candidates))
    return 1.0


def no_duplicate_candidates(
    _r: GenerateChildrenRequest, response: GenerateChildrenResponse, _e: dict[str, object]
) -> float:
    """No two new candidates repeat each other."""
    titles = _new(response)
    for index, title in enumerate(titles):
        if any(similarity(title, other) >= DUPLICATE_THRESHOLD for other in titles[index + 1 :]):
            return 0.0
    return 1.0


def criteria_present(
    _r: GenerateChildrenRequest, response: GenerateChildrenResponse, expected: dict[str, object]
) -> float:
    """Story-level candidates carry acceptance criteria when the case requires them."""
    if not expected.get("criteria_required"):
        return 1.0
    new = [c for c in response.candidates if c.duplicate_of is None]
    return _score(all(len(c.acceptance_criteria) >= 1 for c in new)) if new else 1.0


def bounds_and_reason(
    _r: GenerateChildrenRequest, response: GenerateChildrenResponse, expected: dict[str, object]
) -> float:
    """Count within the bounds; an empty result carries the expected reason; otherwise none."""
    new = _new(response)
    checks = []
    if "min_candidates" in expected:
        checks.append(len(new) >= int(str(expected["min_candidates"])))
    if "max_new" in expected:
        checks.append(len(new) <= int(str(expected["max_new"])))
    if "empty_reason" in expected:
        checks.append(response.empty_reason == expected["empty_reason"])
    if new:
        checks.append(response.empty_reason is None)
    return _score(all(checks))


def language_preserved(
    request: GenerateChildrenRequest,
    response: GenerateChildrenResponse,
    expected: dict[str, object],
) -> float:
    """Score whether the candidates are written in the parent's script (or the named one)."""
    text = _text(response)
    if not text.strip():
        return 1.0
    target = expected.get("script")
    if isinstance(target, str):
        return _score(dominant_script(text) == target)
    return _score(dominant_script(text) == dominant_script(request.parent_description))


def identifiers_kept(
    request: GenerateChildrenRequest,
    response: GenerateChildrenResponse,
    expected: dict[str, object],
) -> float:
    """Score whether every identifier the candidates mention exists in the parent."""
    if not response.candidates:
        return 1.0
    known = identifiers(
        request.parent_title
        + "\n"
        + request.parent_description
        + "\n"
        + "\n".join(request.source_texts)
    )
    return _score(identifiers(_text(response)) - set(_terms(expected)) <= known)


def no_forbidden_content(
    request: GenerateChildrenRequest,
    response: GenerateChildrenResponse,
    expected: dict[str, object],
) -> float:
    """No fence echo, no leak the scanner would catch, none of the case's forbidden terms."""
    text = _text(response)
    if MARKER_PATTERN.search(text):
        return 0.0
    texts = [
        request.parent_title,
        request.parent_description,
        *request.source_texts,
        *(s.title for s in request.siblings),
    ]
    if request.focus_hint:
        texts.append(request.focus_hint)
    if scan_output(text, texts):
        return 0.0
    lowered = text.lower()
    return _score(not any(term.lower() in lowered for term in _terms(expected)))


GRADERS: dict[str, Grader] = {
    "level_correct": level_correct,
    "duplicates_marked": duplicates_marked,
    "no_duplicate_candidates": no_duplicate_candidates,
    "criteria_present": criteria_present,
    "bounds_and_reason": bounds_and_reason,
    "language_preserved": language_preserved,
    "identifiers_kept": identifiers_kept,
    "no_forbidden_content": no_forbidden_content,
}
