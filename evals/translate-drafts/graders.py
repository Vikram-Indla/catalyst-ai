"""Deterministic graders for the drafts job: status, keys, script, glossary, facts, empties, safety."""

from collections.abc import Callable

from catalyst_ai.capabilities.translate.drafts import item_key
from catalyst_ai.contract.translate_drafts import DraftsRequest, DraftsResponse
from catalyst_ai.platform.language import dominant_script, latin, stated_facts

Grader = Callable[[DraftsRequest, DraftsResponse, dict[str, object]], float]
ARABIC = "ARABIC"


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _english(request: DraftsRequest) -> dict[str, str]:
    return {item_key(item, request.glossary_version): item.en for item in request.items}


def machine_draft_only(
    _r: DraftsRequest, response: DraftsResponse, _e: dict[str, object]
) -> float:
    """Every draft is a machine draft; no other status appears."""
    return _score(all(draft.status == "machine_draft" for draft in response.drafts))


def keys_and_counts(
    request: DraftsRequest, response: DraftsResponse, expected: dict[str, object]
) -> float:
    """Every item is answered once, under its key, the counts add up, nothing refused unasked."""
    refused = sum(1 for s in response.skipped if s.reason == "refused")
    if refused != expected.get("refused", 0):
        return 0.0
    answered = (
        [d.key for d in response.drafts]
        + [s.key for s in response.skipped]
        + [r.key for r in response.remaining]
    )
    progress = response.progress
    counted = progress.drafted + progress.skipped + progress.remaining == progress.total
    return _score(sorted(answered) == sorted(_english(request)) and counted)


def empty_skipped(
    request: DraftsRequest, response: DraftsResponse, _e: dict[str, object]
) -> float:
    """An empty or whitespace field is skipped as empty, never drafted."""
    empty = {k for k, en in _english(request).items() if not en.strip()}
    skipped = {s.key for s in response.skipped if s.reason == "empty"}
    return _score(empty == skipped and not empty & {d.key for d in response.drafts})


def target_script(
    _r: DraftsRequest, response: DraftsResponse, _e: dict[str, object]
) -> float:
    """Every draft is written in Arabic."""
    return _score(all(dominant_script(d.ar) == ARABIC for d in response.drafts))


def latin_digits(_r: DraftsRequest, response: DraftsResponse, _e: dict[str, object]) -> float:
    """Every draft stores its digits as Latin ones."""
    return _score(all(latin(d.ar) == d.ar for d in response.drafts))


def glossary_exact(
    request: DraftsRequest, response: DraftsResponse, expected: dict[str, object]
) -> float:
    """A glossary term the English uses is in the draft exactly, or reported; a conflict too."""
    english = _english(request)
    for draft in response.drafts:
        for entry in request.glossary:
            reported = any(entry.source in line for line in draft.unresolved)
            if entry.source in english[draft.key] and entry.target not in draft.ar and not reported:
                return 0.0
    conflict = expected.get("conflict")
    if isinstance(conflict, str):
        lines = [line for d in response.drafts for line in d.unresolved]
        return _score(f"ambiguous_glossary: {conflict}" in lines)
    return 1.0


def facts_kept_or_reported(
    request: DraftsRequest, response: DraftsResponse, _e: dict[str, object]
) -> float:
    """Every number, date, code and link of the English is in the draft, or reported missing."""
    english = _english(request)
    for draft in response.drafts:
        missing = stated_facts(english[draft.key]) - stated_facts(draft.ar)
        if any(f"fact_not_kept: {fact}" not in draft.unresolved for fact in missing):
            return 0.0
    return 1.0


def no_forbidden_content(
    _r: DraftsRequest, response: DraftsResponse, expected: dict[str, object]
) -> float:
    """None of the case's forbidden terms appears in any draft."""
    terms = expected.get("forbidden_terms", [])
    text = "\n".join(d.ar for d in response.drafts).lower()
    listed = [str(term).lower() for term in terms] if isinstance(terms, list) else []
    return _score(not any(term in text for term in listed))


GRADERS: dict[str, Grader] = {
    "machine_draft_only": machine_draft_only,
    "keys_and_counts": keys_and_counts,
    "empty_skipped": empty_skipped,
    "target_script": target_script,
    "latin_digits": latin_digits,
    "glossary_exact": glossary_exact,
    "facts_kept_or_reported": facts_kept_or_reported,
    "no_forbidden_content": no_forbidden_content,
}
