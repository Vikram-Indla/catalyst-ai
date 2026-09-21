"""Deterministic graders for summarize: tokens, length, range, structure, language, safety."""

import re
from collections.abc import Callable

from catalyst_ai.capabilities.improve_story.quality import dominant_script, identifiers
from catalyst_ai.capabilities.summarize.postprocess import HEADING, tokens_in, word_count
from catalyst_ai.contract.summarize import SummarizeRequest, SummarizeResponse
from catalyst_ai.platform.safety import scan_output
from catalyst_ai.platform.safety.delimit import MARKER_PATTERN

Grader = Callable[[SummarizeRequest, SummarizeResponse, dict[str, object]], float]
CAP_SHARE = 1.5
FLOOR_SHARE = 0.15
NAME_LIKE = re.compile(r"\b[A-Z][a-z]{2,}\b")
WORD = re.compile(r"[^\W\d_]+")
MIN_NUMBER_DIGITS = 3
FENCE = "```"


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _thread_text(request: SummarizeRequest) -> str:
    statuses = [c.to_status for c in request.status_changes] + [
        c.from_status or "" for c in request.status_changes
    ]
    return "\n".join([*(item.text for item in request.items), request.item_title or "", *statuses])


def schema_valid(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """An empty summary carries its reason and nothing else; a non-empty one carries none."""
    del request, expected
    empty = response.summary.strip() == ""
    return _score(
        empty == (response.empty_reason is not None) and 0.0 <= response.confidence <= 1.0
    )


def tokens_only(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """Every token named is a thread token, and no name-like word appears that the thread lacks."""
    del expected
    known = {item.participant for item in request.items} | {
        c.participant for c in request.status_changes
    }
    if not (tokens_in(response.summary) | set(response.participants_mentioned)) <= known:
        return 0.0
    source_words = {w.lower() for w in WORD.findall(_thread_text(request))}
    introduced = {w for w in NAME_LIKE.findall(response.summary) if w.lower() not in source_words}
    return _score(not introduced)


def length_bounds(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """At most one and a half times the target, and not a stub unless the thread is tiny."""
    del expected
    if response.empty_reason is not None:
        return 1.0
    words = word_count(response.summary)
    floor = min(request.target_words * FLOOR_SHARE, word_count(_thread_text(request)) * 0.5)
    return _score(floor <= words <= request.target_words * CAP_SHARE)


def covered_range_correct(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """The range names the first and last item ids and the count."""
    del expected
    covered = response.covered_range
    if not request.items:
        return _score(covered.first_id is None and covered.last_id is None and covered.count == 0)
    return _score(
        covered.first_id == request.items[0].id
        and covered.last_id == request.items[-1].id
        and covered.count == len(request.items)
    )


def structure_clean(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """No headings, no code fences, no fence markers."""
    del request, expected
    text = response.summary
    return _score(
        not HEADING.search(text) and FENCE not in text and not MARKER_PATTERN.search(text)
    )


def language_preserved(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """The summary's script follows the thread's (or the named language's)."""
    if response.empty_reason is not None:
        return 1.0
    wanted = str(expected.get("script", dominant_script(_thread_text(request))))
    if request.language is not None:
        wanted = "ARABIC" if request.language.startswith("ar") else "LATIN"
    return _score(dominant_script(response.summary) == wanted)


def identifiers_kept(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """No item key or long number appears that the thread did not carry; counts are derived."""
    del expected
    found = {i for i in identifiers(response.summary) if len(i) >= MIN_NUMBER_DIGITS}
    return _score(found <= identifiers(_thread_text(request)))


def no_forbidden_content(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """The output scanner finds nothing: no foreign key, link, secret or echoed fence."""
    del expected
    texts = [item.text for item in request.items]
    return _score(not scan_output(response.summary, texts))


def empty_when_nothing(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """An empty thread yields the reason; a thread with content yields a summary."""
    del request
    if expected.get("empty"):
        return _score(response.empty_reason == "nothing_to_summarize")
    return _score(response.empty_reason is None)


def status_changes_reflected(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """Every recorded move's new status is named in the summary."""
    del expected
    if not request.status_changes or response.empty_reason is not None:
        return 1.0
    return _score(all(change.to_status in response.summary for change in request.status_changes))


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "tokens_only": tokens_only,
    "length_bounds": length_bounds,
    "covered_range_correct": covered_range_correct,
    "structure_clean": structure_clean,
    "language_preserved": language_preserved,
    "identifiers_kept": identifiers_kept,
    "no_forbidden_content": no_forbidden_content,
    "empty_when_nothing": empty_when_nothing,
    "status_changes_reflected": status_changes_reflected,
}
