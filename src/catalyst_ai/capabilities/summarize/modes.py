"""The window modes: what standup and digest need at the door and how their shapes are laid out."""

from catalyst_ai.capabilities.summarize.schema import ModelOutput
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.summarize import (
    MAX_LINE_CHARS,
    MAX_LINES,
    WINDOW_MODES,
    DigestGroup,
    StandupEntry,
    SummarizeRequest,
)
from catalyst_ai.platform.errors import Error

WINDOW_REQUIRED = "window_required"
COUNTS_REQUIRED = "counts_required"
ELLIPSIS = " …"


def is_window_mode(request: SummarizeRequest) -> bool:
    """Whether the mode covers a span rather than a thread."""
    return request.mode.value in WINDOW_MODES


def require_window(request: SummarizeRequest) -> None:
    """Refuse a standup or digest without its window, and a digest without the counts."""
    if not is_window_mode(request):
        return
    if request.window is None:
        detail = ErrorDetail(field="window", code=WINDOW_REQUIRED, message="the mode needs a span")
        raise Error(ErrorCode.INPUT_REJECTED, "the request names no window", details=[detail])
    if request.mode.value == "digest" and not request.counts:
        detail = ErrorDetail(
            field="counts", code=COUNTS_REQUIRED, message="a digest echoes the backend's counts"
        )
        raise Error(ErrorCode.INPUT_REJECTED, "the request carries no counts", details=[detail])


def within_window(request: SummarizeRequest) -> SummarizeRequest:
    """Return the request with only the items and moves inside its window, in their order."""
    if request.window is None:
        return request
    start, end = request.window.from_at, request.window.to_at
    return request.model_copy(
        update={
            "items": [item for item in request.items if start <= item.at <= end],
            "status_changes": [c for c in request.status_changes if start <= c.at <= end],
        }
    )


def window_text(request: SummarizeRequest) -> str:
    """Return the span as the prompt reads it."""
    if request.window is None:
        return ""
    return f"{request.window.from_at.isoformat()} to {request.window.to_at.isoformat()}"


def counts_text(request: SummarizeRequest) -> str:
    """One `kind: count` per line — the only counts a digest may state."""
    return "\n".join(f"{c.kind}: {c.count}" for c in request.counts)


def clean_lines(lines: list[str]) -> list[str]:
    """Trim, drop empties, cut at the line budget and the line length."""
    kept = []
    for line in lines:
        text = line.strip().lstrip("-•* ").strip()
        if text:
            kept.append(
                text if len(text) <= MAX_LINE_CHARS else text[: MAX_LINE_CHARS - 2] + ELLIPSIS
            )
    return kept[:MAX_LINES]


def standup_entries(output: ModelOutput, request: SummarizeRequest) -> list[StandupEntry]:
    """One entry per participant in the items, in token order; the model's lines, cleaned."""
    if request.mode.value != "standup":
        return []
    by_token = {entry.participant: entry for entry in output.standup}
    known = sorted({item.participant for item in request.items}, key=lambda t: int(t[1:]))
    entries = []
    for token in known:
        entry = by_token.get(token)
        entries.append(
            StandupEntry(
                participant=token,
                done=clean_lines(entry.done) if entry else [],
                doing=clean_lines(entry.doing) if entry else [],
                blocked=clean_lines(entry.blocked) if entry else [],
            )
        )
    return entries


def digest_groups(output: ModelOutput, request: SummarizeRequest) -> list[DigestGroup]:
    """One group per kind the backend counted, in its order, with its count — never the model's."""
    if request.mode.value != "digest":
        return []
    by_kind = {group.kind: group for group in output.digest}
    return [
        DigestGroup(
            kind=count.kind,
            count=count.count,
            changes=clean_lines(by_kind[count.kind].changes) if count.kind in by_kind else [],
        )
        for count in request.counts
    ]


def lines_of(entries: list[StandupEntry], groups: list[DigestGroup]) -> str:
    """Every line of both shapes, joined — what the participant rule and the scanner read."""
    standup = [line for e in entries for line in [*e.done, *e.doing, *e.blocked]]
    digest = [line for g in groups for line in g.changes]
    return "\n".join(standup + digest)
