"""Doubles for the storage seam: a document builder and a hashed vector, shared by both stores."""

import dataclasses
from typing import Any
from uuid import UUID

from catalyst_ai.platform.storage import ChunkRow, DocumentRecord
from tests.unit.capabilities.improve_story.conftest import hashed_vector

ORG_A = UUID("aaaaaaaa-aaaa-7aaa-8aaa-aaaaaaaaaaaa")
ORG_B = UUID("bbbbbbbb-bbbb-7bbb-8bbb-bbbbbbbbbbbb")
MODEL = "double"
VERSION = "d64-r1"
HASH = "0" * 64


BASE = DocumentRecord(
    organization_id=ORG_A,
    corpus="work_items",
    external_id="",
    kind="story",
    title=None,
    text="",
    content_hash=HASH,
    data_class="CONFIDENTIAL",
    embedding_model=MODEL,
    embedding_version=VERSION,
)


def document(
    organization_id: UUID, external_id: str, text: str, **overrides: Any
) -> DocumentRecord:
    return dataclasses.replace(
        BASE, organization_id=organization_id, external_id=external_id, text=text, **overrides
    )


def chunks(*texts: str) -> list[ChunkRow]:
    return [ChunkRow(i, text, tuple(hashed_vector(text))) for i, text in enumerate(texts)]
