"""Deterministic graders for summarize: tokens, length, range, structure, windows, safety."""

import re
from collections.abc import Callable

from catalyst_ai.capabilities.summarize.modes import lines_of, within_window
from catalyst_ai.capabilities.summarize.postprocess import HEADING, word_count
from catalyst_ai.contract.summarize import CHAT_HEADINGS, SummarizeRequest, SummarizeResponse
from catalyst_ai.platform.language.records import tokens_in
from catalyst_ai.platform.language.signals import (
    ITEM_KEY,
    NUMBER,
    dominant_script,
    identifiers,
)
from catalyst_ai.platform.safety import scan_output
from catalyst_ai.platform.safety.delimit import MARKER_PATTERN

Grader = Callable[[SummarizeRequest, SummarizeResponse, dict[str, object]], float]
CAP_SHARE = 1.5
FLOOR_SHARE = 0.15
NAME_LIKE = re.compile(r"(?<=[a-z,;] )[A-Z][a-z]{2,}\b")
WORD = re.compile(r"[^\W\d_]+")
MIN_NUMBER_DIGITS = 3
FENCE = "```"


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _text(response: SummarizeResponse) -> str:
    return response.summary + "\n" + lines_of(response.standup, response.digest, response.chat)


def _strings(expected: dict[str, object], name: str) -> list[str]:
    value = expected.get(name, [])
    return [str(v) for v in value] if isinstance(value, list) else []


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
    if not (tokens_in(_text(response)) | set(response.participants_mentioned)) <= known:
        return 0.0
    source_words = {w.lower() for w in WORD.findall(_thread_text(request))}
    introduced = {w for w in NAME_LIKE.findall(_text(response)) if w.lower() not in source_words}
    return _score(not introduced)


def length_bounds(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """At most one and a half times the target, and not a stub unless the thread is tiny."""
    del expected
    if response.empty_reason is not None:
        return 1.0
    words = word_count(_text(response))
    floor = min(request.target_words * FLOOR_SHARE, word_count(_thread_text(request)) * 0.5)
    return _score(floor <= words <= request.target_words * CAP_SHARE)


def covered_range_correct(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """The range names the first and last item ids and the count."""
    del expected
    covered = response.covered_range
    items = within_window(request).items
    if not items:
        return _score(covered.first_id is None and covered.last_id is None and covered.count == 0)
    return _score(
        covered.first_id == items[0].id
        and covered.last_id == items[-1].id
        and covered.count == len(items)
    )


def structure_clean(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """No headings, no code fences, no fence markers."""
    del request, expected
    text = _text(response)
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
    return _score(dominant_script(_text(response)) == wanted)


def identifiers_kept(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """No item key or long number appears that the thread did not carry; counts are derived."""
    del expected
    found = {i for i in identifiers(_text(response)) if len(i) >= MIN_NUMBER_DIGITS}
    return _score(found <= identifiers(_thread_text(request)))


def no_forbidden_content(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """The output scanner finds nothing: no foreign key, link, secret or echoed fence."""
    del expected
    texts = [item.text for item in request.items]
    return _score(not scan_output(_text(response), texts))


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


def standup_shape(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """A standup has one entry per token inside the window, in token order, and nothing else."""
    del expected
    if request.mode.value != "standup" or response.empty_reason is not None:
        return _score(not response.standup)
    tokens = sorted({i.participant for i in within_window(request).items}, key=lambda t: int(t[1:]))
    return _score([e.participant for e in response.standup] == tokens and not response.digest)


def digest_shape_and_count_echo(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """A digest has one group per counted kind, in the request's order, with the request's count."""
    del expected
    if request.mode.value != "digest" or response.empty_reason is not None:
        return _score(not response.digest)
    wanted = [(c.kind, c.count) for c in request.counts]
    return _score([(g.kind, g.count) for g in response.digest] == wanted and not response.standup)


def window_respected(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """Nothing from outside the window is named: no outside id, no key only an outside item has."""
    inside = {i.id for i in within_window(request).items}
    outside_keys: set[str] = set()
    inside_keys: set[str] = set()
    for item in request.items:
        keys = set(ITEM_KEY.findall(item.text))
        (inside_keys if item.id in inside else outside_keys).update(keys)
    text = _text(response)
    leaked = (outside_keys - inside_keys) & set(ITEM_KEY.findall(text))
    outside_ids = [i for i in _strings(expected, "outside_ids") if i in text]
    return _score(not leaked and not outside_ids)


def no_counts_invented(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """A digest states no number the data did not carry; the counts are echoed as fields only."""
    del expected
    if request.mode.value != "digest":
        return 1.0
    source = set(NUMBER.findall(_thread_text(request)))
    return _score(set(NUMBER.findall(_text(response))) <= source)


def chat_shape(
    request: SummarizeRequest, response: SummarizeResponse, expected: dict[str, object]
) -> float:
    """Score a chat summary as the four fixed headings in order, its lines by token, else none."""
    del expected
    if request.mode.value != "chat" or response.empty_reason is not None:
        return _score(not response.chat)
    headings = [s.heading for s in response.chat]
    tokens = {i.participant for i in request.items}
    named = all(line.split(":")[0] in tokens for s in response.chat for line in s.lines)
    return _score(headings == list(CHAT_HEADINGS) and named and not response.standup)


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
    "standup_shape": standup_shape,
    "digest_shape_and_count_echo": digest_shape_and_count_echo,
    "window_respected": window_respected,
    "no_counts_invented": no_counts_invented,
    "chat_shape": chat_shape,
}
