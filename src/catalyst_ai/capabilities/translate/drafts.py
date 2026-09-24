"""The drafts job: each field through the translate pipeline, keyed, in Latin digits, facts checked.

Every item runs the translate pipeline English → Arabic with the batch's glossary, under its own
key as the idempotency key, so a resubmitted batch answers drafted items from the cache and drafts
only the rest. The draft's digits are Latin, as stored. A number, key, link or date the English
states and the Arabic does not, or the reverse, is reported in `unresolved` beside the glossary's
conflicts: the draft goes to a reviewer, and the reviewer is told. A budget, provider or time stop
ends the run; the items not reached are `remaining`.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.pipeline import run
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.translate import TranslateMode, TranslateRequest, TranslateResponse
from catalyst_ai.contract.translate_drafts import (
    Draft,
    DraftItem,
    DraftProgress,
    DraftsRequest,
    DraftsResponse,
    Remaining,
    RemainingReason,
    Skipped,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language import latin, stated_facts
from catalyst_ai.platform.runtime import RuntimeContext

SEPARATOR = "\x1f"
SOURCE = "en"
TARGET = "ar"
DEADLINE_SHARE = 0.8
NO_MODEL = "none"
STOPS: MappingProxyType[ErrorCode, RemainingReason] = MappingProxyType(
    {
        ErrorCode.BUDGET_EXCEEDED: "budget_exhausted",
        ErrorCode.PROVIDER_UNAVAILABLE: "provider_unavailable",
        ErrorCode.PROVIDER_TIMEOUT: "provider_unavailable",
        ErrorCode.PROVIDER_QUOTA: "provider_unavailable",
    }
)


def item_key(item: DraftItem, glossary_version: str) -> str:
    """Return the item's key: its record, its field, the hash of its text, the glossary version."""
    text_hash = hashlib.sha256(item.en.encode()).hexdigest()
    parts = (item.record_ref, item.field, text_hash, glossary_version)
    return hashlib.sha256(SEPARATOR.join(parts).encode()).hexdigest()


def unresolved(english: str, response: TranslateResponse) -> list[str]:
    """Return the glossary's conflicts and every fact the draft drops or adds, for the reviewer."""
    source, draft = stated_facts(english), stated_facts(response.translated_text)
    conflicts = [f"{c.reason}: {c.source}" for c in response.glossary_conflict]
    dropped = [f"fact_not_kept: {fact}" for fact in sorted(source - draft)]
    added = [f"fact_added: {fact}" for fact in sorted(draft - source)]
    return conflicts + dropped + added


@dataclass
class Tally:
    """What a run has produced so far."""

    drafts: list[Draft] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    remaining: list[Remaining] = field(default_factory=list)
    responses: list[TranslateResponse] = field(default_factory=list)
    stop: RemainingReason | None = None

    def draft(self, key: str, item: DraftItem, response: TranslateResponse) -> None:
        """Record one item's draft."""
        self.responses.append(response)
        self.drafts.append(
            Draft(
                key=key,
                record_ref=item.record_ref,
                field=item.field,
                ar=latin(response.translated_text),
                glossary_hits=list(response.glossary_applied),
                unresolved=unresolved(item.en, response),
            )
        )

    def refuse(self, key: str, item: DraftItem, error: Error) -> None:
        """Record an item the pipeline refused; a stop ends the run instead."""
        self.stop = STOPS.get(error.code)
        if self.stop is None:
            self.skipped.append(
                Skipped(
                    key=key,
                    record_ref=item.record_ref,
                    field=item.field,
                    reason="refused",
                    code=error.code.value,
                )
            )
        else:
            self.leave(key, item)

    def leave(self, key: str, item: DraftItem) -> None:
        """Record an item this run does not reach."""
        reason = self.stop or "time_exhausted"
        self.remaining.append(
            Remaining(key=key, record_ref=item.record_ref, field=item.field, reason=reason)
        )


def _request(request: DraftsRequest, item: DraftItem) -> TranslateRequest:
    return TranslateRequest(
        organization_id=request.organization_id,
        capability_version=request.capability_version,
        mode=TranslateMode.FIELD,
        text=item.en,
        source_language=SOURCE,
        target_language=TARGET,
        glossary=request.glossary,
    )


def _deadline(runtime: RuntimeContext) -> datetime:
    seconds = runtime.settings.job_timeout_seconds * DEADLINE_SHARE
    return runtime.clock.now() + timedelta(seconds=seconds)


async def run_drafts(
    request: DraftsRequest, runtime: RuntimeContext, request_id: str
) -> DraftsResponse:
    """Draft every item it can reach, in order; report the rest."""
    tally = Tally()
    deadline = _deadline(runtime)
    for index, item in enumerate(request.items):
        key = item_key(item, request.glossary_version)
        if tally.stop is None and runtime.clock.now() >= deadline:
            tally.stop = "time_exhausted"
        if tally.stop is not None:
            tally.leave(key, item)
        elif not item.en.strip():
            tally.skipped.append(
                Skipped(key=key, record_ref=item.record_ref, field=item.field, reason="empty")
            )
        else:
            item_id = f"{request_id}:{index}"
            outcome = await _translate(_request(request, item), runtime, item_id, key)
            if isinstance(outcome, Error):
                tally.refuse(key, item, outcome)
            else:
                tally.draft(key, item, outcome)
    return _response(tally, len(request.items), request_id)


async def _translate(
    request: TranslateRequest, runtime: RuntimeContext, request_id: str, key: str
) -> TranslateResponse | Error:
    try:
        return await run(request, runtime, request_id, idempotency=key)
    except Error as error:
        return error


def _usage(responses: list[TranslateResponse]) -> Usage:
    usages = [r.usage for r in responses]
    return Usage(
        input_tokens=sum(u.input_tokens for u in usages),
        output_tokens=sum(u.output_tokens for u in usages),
        cost_micros=sum(u.cost_micros for u in usages),
        latency_ms=sum(u.latency_ms for u in usages),
        cache_hit=bool(usages) and all(u.cache_hit for u in usages),
    )


def _response(tally: Tally, total: int, request_id: str) -> DraftsResponse:
    cached = sum(1 for r in tally.responses if r.usage.cache_hit)
    model = tally.responses[0].model if tally.responses else f"{descriptor.alias}@{NO_MODEL}"
    return DraftsResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=model,
        eval_set_version=descriptor.eval_set_version,
        usage=_usage(tally.responses),
        request_id=request_id,
        drafts=tally.drafts,
        skipped=tally.skipped,
        remaining=tally.remaining,
        progress=DraftProgress(
            total=total,
            drafted=len(tally.drafts),
            skipped=len(tally.skipped),
            remaining=len(tally.remaining),
            from_cache=cached,
        ),
    )
