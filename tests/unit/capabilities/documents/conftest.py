"""Doubles for documents: request builders, a seeded space, well-formed completions."""

import base64
import hashlib
import json
from typing import Any

from catalyst_ai.capabilities.documents import run_ingest
from catalyst_ai.contract.documents import AskRequest, DraftRequest, IngestRequest
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.improve_story.conftest import ORG, ScriptedProvider, make_runtime

SPACE = "kb-main"
RUNBOOK = (
    "# Incident runbook\n\n## Paging\n\nAlerts page the on-call engineer through the paging "
    "service.\n\nThe on-call rota changes every Sunday at nine.\n\n## Rollback\n\nA rollback "
    "needs the release manager's approval in the release hub.\n"
)
EXPORT = "# Board export\n\n## Limits\n\nAn export covers at most five thousand rows.\n"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def ingest_request(**overrides: object) -> IngestRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "space_id": SPACE,
        "document_id": "doc-runbook",
        "kind": "wiki_page",
        "format": "markdown",
        "title": "Incident runbook",
        "text": RUNBOOK,
        "data_class": "INTERNAL",
        "content_hash": sha(RUNBOOK),
    }
    values.update(overrides)
    return IngestRequest.model_validate(values)


def bytes_request(payload: bytes, fmt: str, **overrides: object) -> IngestRequest:
    return ingest_request(
        text=None,
        content_base64=base64.b64encode(payload).decode(),
        format=fmt,
        content_hash=hashlib.sha256(payload).hexdigest(),
        **overrides,
    )


def ask_request(**overrides: object) -> AskRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "space_id": SPACE,
        "question": "Who approves a rollback?",
        "k": 4,
    }
    values.update(overrides)
    return AskRequest.model_validate(values)


def draft_request(**overrides: object) -> DraftRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "brief": "Write a short guide to incidents and exports.",
        "sources": [
            {"id": "src-runbook", "title": "Incident runbook", "text": RUNBOOK},
            {"id": "src-export", "title": "Board export", "text": EXPORT},
        ],
        "target_words": 100,
    }
    values.update(overrides)
    return DraftRequest.model_validate(values)


async def seeded_runtime(texts: list[str]) -> RuntimeContext:
    """A runtime whose memory index holds the runbook and the export in the space."""
    runtime = make_runtime(ScriptedProvider(texts))
    await run_ingest(ingest_request(), runtime, "seed-1")
    await run_ingest(
        ingest_request(
            document_id="doc-export",
            kind="attachment",
            title="Board export",
            text=EXPORT,
            content_hash=sha(EXPORT),
        ),
        runtime,
        "seed-2",
    )
    return runtime


def answer_text(claims: list[dict[str, Any]] | None = None, *, not_found: bool = False) -> str:
    default = [
        {
            "text": "A rollback needs the release manager's approval.",
            "chunk_ids": ["kb-main/doc-runbook#1"],
        }
    ]
    return json.dumps(
        {"claims": default if claims is None else claims, "not_found": not_found, "rationale": "r"}
    )


def draft_text(
    sections: list[dict[str, Any]] | None = None, empty_reason: str | None = None
) -> str:
    default = [
        {
            "heading": "Incidents",
            "text": "Alerts page the on-call engineer.",
            "sources": ["src-runbook"],
        },
        {
            "heading": "Exports",
            "text": "An export covers at most five thousand rows.",
            "sources": ["src-export"],
        },
    ]
    return json.dumps(
        {
            "title": "Guide",
            "sections": default if sections is None else sections,
            "empty_reason": empty_reason,
            "rationale": "r",
        }
    )
