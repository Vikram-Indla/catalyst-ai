"""A development-only stand-in for the model: fixed, marked answers, to walk the round trip.

No model is called and nothing leaves the machine. The stand-in answers the three operations of a
record's Improve menu (`improve-story`, `generate-children`, `summarize`) and the command centre's
briefing (`brief`) with fixed text that says it is a stand-in, and the capabilities' own rules
judge it as they judge a model. So the walk shows the real behaviour:
- **a proposal:** the text comes back as written, marked, so every fact survives; a text that
  opens with a markdown heading keeps it first, the mark inside its section, so sections split
  back the way they were sent;
- **a withheld refusal:** when the member's focus hint names a number, the stand-in writes it in,
  and the governed-record rule refuses it (`fact_added`), because a hint is not a source;
- **draft children:** two marked drafts, plus a third carrying a figure, which draft-only mode
  withholds and counts;
- **a summary:** one marked line;
- **a briefing:** marked sentences, each citing the chain's own ids (the brief's rule refuses a
  citation outside the chain), no number at all, and one line the chain does not support, shown
  as "not stated in the data".

Every other operation answers `ai.provider.unavailable`. Embeddings are deterministic vectors
drawn from each text's hash, so indexing and similar-item search run, with no meaning. The
settings refuse the stand-in outside development (`config/deployed.py`).
"""

import hashlib
import json
import math
import re
from collections.abc import AsyncIterator, Callable, Mapping
from types import MappingProxyType

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.models import ModelAlias
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    Segment,
    StreamFrame,
)

MARK = "Stand-in suggestion, no model:"
MODEL_ID = "development-stand-in"
DIMENSIONS = 768
CHARS_PER_TOKEN = 4
DIGITS = re.compile(r"\d+(?:[.,]\d+)?%?")
WITHHELD_FIGURE = "Reach 50% adoption"
RETRY_AFTER_MS = 60_000
RATIONALE = "The development stand-in returns fixed text; no model read the input."
CHAIN_ID = re.compile(r"^\s*(?P<kind>[a-z ]+?) \[(?P<id>[^\]]+)\]", re.MULTILINE)
NOT_IN_CHAIN = "Whether the targets will be met: a stand-in cannot tell."


def fenced(segments: list[Segment], name: str) -> str:
    """Return the text of the named fence in any segment, or an empty string."""
    pattern = re.compile(
        rf"<<<{re.escape(name)}>>>\n(?P<body>.*?)\n<<<end {re.escape(name)}>>>", re.S
    )
    for segment in segments:
        found = pattern.search(segment.text)
        if found:
            return found.group("body").strip()
    return ""


def improve(segments: list[Segment]) -> dict[str, object]:
    """Return the text as written, marked; a number the hint names is written in, to be withheld."""
    text = fenced(segments, "description")
    figure = DIGITS.search(fenced(segments, "focus_hint"))
    added = f" Target: {figure.group(0)}." if figure else ""
    heading, _, body = text.partition("\n") if text.startswith("#") else ("", "", text)
    marked = f"{heading}\n\n{MARK} {body.lstrip()}" if heading else f"{MARK} {text}"
    return {
        "description": f"{marked}{added}",
        "acceptance_criteria": None,
        "rationale": RATIONALE,
        "changed": True,
    }


def children(segments: list[Segment]) -> dict[str, object]:
    """Return two marked drafts at the child level, and a third with a figure to be withheld."""
    level = fenced(segments, "child_level") or "child"
    drafts = [f"{MARK} first draft", f"{MARK} second draft", f"{MARK} {WITHHELD_FIGURE}"]
    candidates = [
        {"type": level, "title": title, "description": title, "acceptance_criteria": []}
        for title in drafts
    ]
    return {"candidates": candidates, "empty_reason": None, "rationale": RATIONALE}


def summary(segments: list[Segment]) -> dict[str, object]:
    """Return one marked line; nobody is named."""
    del segments
    return {
        "summary": f"{MARK} this is where the thread's summary appears.",
        "participants_mentioned": [],
        "empty_reason": None,
        "rationale": RATIONALE,
    }


def briefing(segments: list[Segment]) -> dict[str, object]:
    """Return marked sentences citing the chain's ids, and one line the chain cannot support."""
    found = {
        m.group("kind"): m.group("id")
        for m in reversed(list(CHAIN_ID.finditer(fenced(segments, "chain"))))
    }
    theme = found.get("theme")
    if theme is None:
        return {"empty_reason": "nothing_to_brief", "rationale": RATIONALE}
    first = found.get("objective", theme)
    risk = found.get("project", found.get("finding", theme))
    summary = [
        {"text": f"{MARK} this briefing covers the theme.", "cites": [theme]},
        {"text": f"{MARK} its objectives are listed as the chain records them.", "cites": [first]},
        {"text": f"{MARK} no model has read the chain.", "cites": [theme]},
    ]
    return {
        "summary": summary,
        "highlights": [{"text": f"{MARK} the first objective, as recorded.", "cites": [first]}],
        "risks": [{"text": f"{MARK} delivery and strategy are shown apart.", "cites": [risk]}],
        "asks": [],
        "unsupported": [NOT_IN_CHAIN],
        "rationale": RATIONALE,
    }


ANSWERS: Mapping[str, Callable[[list[Segment]], dict[str, object]]] = MappingProxyType(
    {
        "improve-story": improve,
        "generate-children": children,
        "summarize": summary,
        "brief": briefing,
    }
)


def vector(text: str) -> list[float]:
    """Return a unit vector drawn from the text's hash: the same text, the same vector."""
    seed = hashlib.sha256(text.encode()).digest()
    raw = [((seed[i % len(seed)] ^ (i * 31)) % 255) / 127.0 - 1.0 for i in range(DIMENSIONS)]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return [v / norm for v in raw]


class StandInProvider:
    """The port, answered without a model; development only."""

    def _tokens(self, text: str) -> int:
        return max(1, len(text) // CHARS_PER_TOKEN)

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Answer an Improve-menu operation with its fixed text; refuse any other."""
        answer = ANSWERS.get(request.capability)
        if answer is None:
            message = f"the development stand-in answers only {sorted(ANSWERS)}"
            raise Error(ErrorCode.PROVIDER_UNAVAILABLE, message, retry_after_ms=RETRY_AFTER_MS)
        text = json.dumps(answer(request.segments), ensure_ascii=False)
        prompt = sum(self._tokens(segment.text) for segment in request.segments)
        usage = Usage(
            input_tokens=prompt,
            output_tokens=self._tokens(text),
            cost_micros=0,
            latency_ms=0,
            cache_hit=False,
        )
        return GenerateResult(text=text, model_id=MODEL_ID, usage=usage)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Refuse streaming: the Improve menu streams nothing."""
        del request
        yield StreamFrame(kind="error", error_code=ErrorCode.PROVIDER_UNAVAILABLE.value)

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        """Return deterministic vectors, one per text."""
        tokens = sum(self._tokens(text) for text in request.texts)
        usage = Usage(
            input_tokens=tokens, output_tokens=0, cost_micros=0, latency_ms=0, cache_hit=False
        )
        return EmbedResult(
            vectors=[vector(t) for t in request.texts], model_id=MODEL_ID, usage=usage
        )

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        """Estimate tokens by characters."""
        del alias
        return self._tokens(text)

    def model_id(self, alias: ModelAlias) -> str:
        """Return the stand-in's name for every alias."""
        del alias
        return MODEL_ID

    async def credentials_ready(self) -> bool:
        """Return true: the stand-in needs no credential."""
        return True
