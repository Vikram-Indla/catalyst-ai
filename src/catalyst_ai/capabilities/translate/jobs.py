"""Drafts as a job: the submission runs the door over every item; the worker drafts them.

The door at submission is the translate door — the switch, the contract version, the scanner over
every item's text (a `RESTRICTED` text is refused before anything is stored) and the tenant cap.
The worker parses the stored payload as the request it always was; nothing else is trusted.
"""

from fastapi import Request
from pydantic import ValidationError

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.drafts import run_drafts
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.jobs import JobAccepted
from catalyst_ai.contract.translate_drafts import DraftsRequest, DraftsResponse
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.jobs import submit
from catalyst_ai.platform.pipeline import Door, admit
from catalyst_ai.platform.runtime import RuntimeContext


def admit_drafts(request: DraftsRequest, runtime: RuntimeContext) -> None:
    """Run the translate door over the batch: switch, version, every item's text, tenant cap."""
    texts: dict[str, str | None] = {
        f"items[{index}].en": item.en for index, item in enumerate(request.items)
    }
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_translate,
        organization_id=request.organization_id,
        capability_version=request.capability_version,
        user_texts=texts,
        canonical_input={},
        idempotency=None,
    )
    admit(door, runtime)


async def submit_drafts(
    body: DraftsRequest, request: Request, runtime: RuntimeContext
) -> tuple[JobAccepted, str]:
    """Run the door synchronously, then store the verified request as a job."""
    admit_drafts(body, runtime)
    return await submit(request, descriptor.name, runtime.jobs, runtime.clock.now())


async def run_drafts_payload(
    payload: bytes, runtime: RuntimeContext, request_id: str
) -> DraftsResponse:
    """Run the stored payload as the request model it always was."""
    try:
        request = DraftsRequest.model_validate_json(payload)
    except ValidationError as error:
        raise Error(
            ErrorCode.VALIDATION_INVALID_INPUT, "the stored payload is not the request"
        ) from error
    return await run_drafts(request, runtime, request_id)
