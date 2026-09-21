"""Doubles for the search capability: request builders over the shared scripted runtime."""

import hashlib

from catalyst_ai.contract.search import IndexDeleteRequest, IndexUpsertRequest, SearchRequest
from tests.unit.capabilities.improve_story.conftest import ORG

VERSION = "1.0.0"


def content_hash(title: str | None, text: str) -> str:
    return hashlib.sha256(f"{title}\n{text}".encode()).hexdigest()


def document(external_id: str, text: str, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "external_id": external_id,
        "kind": "story",
        "title": None,
        "text": text,
        "data_class": "CONFIDENTIAL",
        "content_hash": content_hash(None, text),
    }
    values.update(overrides)
    if "title" in overrides and "content_hash" not in overrides:
        values["content_hash"] = content_hash(str(overrides["title"]), text)
    return values


def upsert_request(*documents: dict[str, object], **overrides: object) -> IndexUpsertRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "corpus": "work_items",
        "documents": list(documents)
        or [
            document("A-1", "The login button is broken on mobile", title="Login broken"),
            document("A-2", "Export the board to CSV with every column", title="Export board"),
        ],
    }
    values.update(overrides)
    return IndexUpsertRequest.model_validate(values)


def delete_request(*external_ids: str, **overrides: object) -> IndexDeleteRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "corpus": "work_items",
        "external_ids": list(external_ids) or ["A-1"],
    }
    values.update(overrides)
    return IndexDeleteRequest.model_validate(values)


def search_request(text: str = "login broken", **overrides: object) -> SearchRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": VERSION,
        "corpus": "work_items",
        "mode": "similar",
        "text": text,
    }
    values.update(overrides)
    return SearchRequest.model_validate(values)
