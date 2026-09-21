"""Deterministic graders for release-notes: traceability, done only, audience, shape, safety."""

from collections.abc import Callable

from catalyst_ai.contract.release_notes import (
    ReleaseNotesRequest,
    ReleaseNotesResponse,
    StatusCategory,
)
from catalyst_ai.platform.language.records import tokens_in
from catalyst_ai.platform.language.signals import ITEM_KEY, dominant_script
from catalyst_ai.platform.safety import scan_output

Grader = Callable[[ReleaseNotesRequest, ReleaseNotesResponse, dict[str, object]], float]
MAX_HIGHLIGHTS = 3


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _entries(response: ReleaseNotesResponse) -> list[tuple[str, str]]:
    pairs = [(e.source_id, e.text) for s in response.sections for e in s.entries]
    return pairs + [(e.source_id, e.text) for e in response.highlights + response.attention]


def _text(response: ReleaseNotesResponse) -> str:
    return "\n".join([response.summary, *(t for _, t in _entries(response))])


def _source_text(request: ReleaseNotesRequest) -> str:
    return "\n".join(f"{c.key or ''} {c.title}\n{c.description or ''}" for c in request.changes)


def schema_valid(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """The mode's shape: notes carry sections, an overview carries a summary; empties are bare."""
    del expected
    if response.empty_reason is not None:
        return _score(not _entries(response) and response.summary == "")
    if request.mode.value == "notes":
        return _score(bool(response.sections) and response.summary == "" and not response.attention)
    return _score(
        bool(response.summary.strip()) and not response.sections and not response.highlights
    )


def no_invented_entries(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """Every entry cites a change the request carried; no change is noted twice in a section."""
    del expected
    ids = {c.id for c in request.changes}
    cited = [i for i, _ in _entries(response)]
    section_ids = [e.source_id for s in response.sections for e in s.entries]
    return _score(set(cited) <= ids and len(section_ids) == len(set(section_ids)))


def done_only_noted(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """Notes name only changes marked done; an overview's attention names only the rest."""
    del expected
    done = {c.id for c in request.changes if c.status_category is StatusCategory.DONE}
    noted = {e.source_id for s in response.sections for e in s.entries}
    noted |= {e.source_id for e in response.highlights}
    attention = {e.source_id for e in response.attention}
    return _score(noted <= done and not (attention & done))


def every_done_change_noted(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """In notes mode every done change has its entry; in-flight lists exactly the rest."""
    del expected
    done = {c.id for c in request.changes if c.status_category is StatusCategory.DONE}
    rest = [c.id for c in request.changes if c.id not in done]
    if response.in_flight != rest:
        return 0.0
    if request.mode.value != "notes" or response.empty_reason is not None:
        return 1.0
    noted = {e.source_id for s in response.sections for e in s.entries}
    return _score(done <= noted)


def keys_traceable(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """No item key appears that the changes did not carry."""
    del expected
    known = {c.key for c in request.changes if c.key} | set(ITEM_KEY.findall(_source_text(request)))
    return _score(set(ITEM_KEY.findall(_text(response))) <= known)


def audience_respected(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """A customer never reads a token; an internal reader reads only the changes' tokens."""
    del expected
    found = tokens_in(_text(response))
    if request.audience.value == "customer":
        return _score(not found)
    return _score(found <= {c.participant for c in request.changes if c.participant})


def highlights_bounded(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """At most three highlights, each also noted in a section."""
    del request, expected
    noted = {e.source_id for s in response.sections for e in s.entries}
    return _score(
        len(response.highlights) <= MAX_HIGHLIGHTS
        and all(h.source_id in noted for h in response.highlights)
    )


def language_preserved(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """The output's script follows the changes' (or the named language's)."""
    if response.empty_reason is not None:
        return 1.0
    wanted = str(expected.get("script", dominant_script(_source_text(request))))
    if request.language is not None:
        wanted = "ARABIC" if request.language.startswith("ar") else "LATIN"
    return _score(dominant_script(_text(response)) == wanted)


def no_forbidden_content(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """The output scanner finds nothing."""
    del expected
    return _score(not scan_output(_text(response), [_source_text(request)]))


def empty_when_nothing(
    request: ReleaseNotesRequest, response: ReleaseNotesResponse, expected: dict[str, object]
) -> float:
    """No done change yields the reason in notes mode; anything else yields content."""
    del request
    if expected.get("empty"):
        return _score(response.empty_reason == "nothing_to_report")
    return _score(response.empty_reason is None)


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "no_invented_entries": no_invented_entries,
    "done_only_noted": done_only_noted,
    "every_done_change_noted": every_done_change_noted,
    "keys_traceable": keys_traceable,
    "audience_respected": audience_respected,
    "highlights_bounded": highlights_bounded,
    "language_preserved": language_preserved,
    "no_forbidden_content": no_forbidden_content,
    "empty_when_nothing": empty_when_nothing,
}
