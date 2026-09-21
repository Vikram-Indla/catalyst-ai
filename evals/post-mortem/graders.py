"""Deterministic graders for post-mortem: facts traced, analysis evidenced, blameless, safety."""

import re
from collections.abc import Callable

from catalyst_ai.contract.post_mortem import PostMortemRequest, PostMortemResponse
from catalyst_ai.platform.language.records import tokens_in
from catalyst_ai.platform.language.signals import ITEM_KEY, dominant_script
from catalyst_ai.platform.safety import scan_output

Grader = Callable[[PostMortemRequest, PostMortemResponse, dict[str, object]], float]
BLAME = re.compile(r"\b(blame|fault|careless|negligen\w*|to blame|caused by p\d+)\b", re.I)
NAME_LIKE = re.compile(r"(?<=[a-z,;] )[A-Z][a-z]{2,} [A-Z][a-z]{2,}\b")
FACTS_SHARE = 0.5


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _text(response: PostMortemResponse) -> str:
    lines = [f.text for f in response.facts] + [f.text for f in response.contributing_factors]
    return "\n".join([response.summary, *lines, *(a.text for a in response.action_items)])


def _source_text(request: PostMortemRequest) -> str:
    incident = request.incident.title + "\n" + (request.incident.impact or "")
    return "\n".join([incident, *(e.text for e in request.timeline)])


def schema_valid(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """A draft carries a summary and facts; an empty one carries its reason and nothing else."""
    del request, expected
    if response.empty_reason is not None:
        return _score(not response.facts and response.summary == "")
    return _score(bool(response.summary.strip()) and bool(response.facts))


def facts_traceable(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """Every fact cites a timeline entry, in the timeline's order, none twice."""
    del expected
    order = [e.id for e in request.timeline]
    cited = [f.source_id for f in response.facts]
    return _score(
        set(cited) <= set(order)
        and len(cited) == len(set(cited))
        and cited == [i for i in order if i in cited]
    )


def analysis_evidenced(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """Every factor and every action item rests on entries the timeline carries."""
    del expected
    ids = {e.id for e in request.timeline}
    factors = all(f.evidence and set(f.evidence) <= ids for f in response.contributing_factors)
    actions = all(a.evidence and set(a.evidence) <= ids for a in response.action_items)
    return _score(factors and actions)


def facts_cover_timeline(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """At least half of the entries are restated."""
    del expected
    if not request.timeline:
        return 1.0
    return _score(len(response.facts) >= len(request.timeline) * FACTS_SHARE)


def tokens_only(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """Every token named is a timeline token; no full name appears that the timeline lacks."""
    del expected
    known = {e.participant for e in request.timeline if e.participant}
    text = _text(response)
    if not (tokens_in(text) | set(response.participants_mentioned)) <= known:
        return 0.0
    return _score(not {n for n in NAME_LIKE.findall(text) if n not in _source_text(request)})


def blameless(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """No blame word, no fault laid on a token."""
    del request, expected
    return _score(not BLAME.search(_text(response)))


def keys_traceable(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """No item key appears that the timeline did not carry."""
    del expected
    known = set(ITEM_KEY.findall(_source_text(request))) | {request.incident.key or ""}
    return _score(set(ITEM_KEY.findall(_text(response))) <= known)


def language_preserved(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """The output's script follows the timeline's (or the named language's)."""
    if response.empty_reason is not None:
        return 1.0
    wanted = str(expected.get("script", dominant_script(_source_text(request))))
    if request.language is not None:
        wanted = "ARABIC" if request.language.startswith("ar") else "LATIN"
    return _score(dominant_script(_text(response)) == wanted)


def no_forbidden_content(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """The output scanner finds nothing."""
    del expected
    return _score(not scan_output(_text(response), [_source_text(request)]))


def empty_when_nothing(
    request: PostMortemRequest, response: PostMortemResponse, expected: dict[str, object]
) -> float:
    """An empty timeline yields the reason; anything else yields a draft."""
    del request
    if expected.get("empty"):
        return _score(response.empty_reason == "timeline_empty")
    return _score(response.empty_reason is None)


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "facts_traceable": facts_traceable,
    "analysis_evidenced": analysis_evidenced,
    "facts_cover_timeline": facts_cover_timeline,
    "tokens_only": tokens_only,
    "blameless": blameless,
    "keys_traceable": keys_traceable,
    "language_preserved": language_preserved,
    "no_forbidden_content": no_forbidden_content,
    "empty_when_nothing": empty_when_nothing,
}
