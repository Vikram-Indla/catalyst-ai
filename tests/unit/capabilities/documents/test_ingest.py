"""The ingest operation: parse under limits, the class rule, the shared index, unchanged, refusals."""

import pytest

from catalyst_ai.capabilities.documents import run_ingest
from catalyst_ai.capabilities.documents.ingest import payload_of, refuse_restricted
from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import SearchScope
from catalyst_ai.retrieval.lexical import web_query
from catalyst_ai.retrieval.parsers import Block, Parsed
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.documents.conftest import (
    bytes_request,
    ingest_request,
    sha,
)
from tests.unit.capabilities.improve_story.conftest import (
    ORG,
    ScriptedProvider,
    make_runtime,
    make_settings,
)

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "documents"


async def test_ingest_indexes_structured_windows_in_the_space() -> None:
    runtime = make_runtime(ScriptedProvider([]))
    response = await run_ingest(ingest_request(), runtime, "r1")
    assert response.state == "indexed"
    assert response.document_id == "doc-runbook"
    assert response.headings == ["Incident runbook > Paging", "Incident runbook > Rollback"]
    assert response.chunks == 2
    assert response.index_chunks == 2
    assert response.embedding_version == "d768-r1"
    scope = SearchScope(ORG, "documents", (), (), 10, "kb-main/")
    hits = await runtime.storage.search_lexical(scope, web_query("rollback approval"))
    assert hits[0].external_id == "kb-main/doc-runbook"
    assert hits[0].text.startswith("§ Incident runbook > Rollback\n")
    again = await run_ingest(ingest_request(), runtime, "r2")
    assert again.state == "unchanged"
    assert again.usage.cost_micros == 0


async def test_bytes_parse_in_the_child_and_hostile_bytes_are_refused_with_a_class() -> None:
    runtime = make_runtime(ScriptedProvider([]))
    docx = (FIXTURES / "benign" / "simple.docx").read_bytes()
    response = await run_ingest(bytes_request(docx, "docx"), runtime, "r")
    assert response.state == "indexed"
    assert response.headings[0] == "Export the board"
    bomb = (FIXTURES / "hostile" / "bomb.docx").read_bytes()
    with pytest.raises(Error) as caught:
        await run_ingest(bytes_request(bomb, "docx"), runtime, "r")
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert caught.value.details[0].code == "document_too_large"
    with pytest.raises(Error) as malformed:
        await run_ingest(bytes_request(b"not a pdf", "pdf"), runtime, "r")
    assert malformed.value.details[0].code == "document_malformed"


def test_payload_and_the_restricted_rule() -> None:
    assert payload_of(ingest_request(text="x")) == b"x"
    assert payload_of(bytes_request(b"\x00\x01", "text")) == b"\x00\x01"
    with pytest.raises(Error) as bad:
        payload_of(ingest_request(text=None, content_base64="***"))
    assert bad.value.details[0].code == "document_malformed"
    refuse_restricted(Parsed([Block((), "nothing restricted here")]))
    with pytest.raises(Error) as caught:
        refuse_restricted(Parsed([Block((), "write to someone@example.com")]))
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert caught.value.details[0].code == "document_restricted"
    assert "example.com" not in caught.value.details[0].message


async def test_restricted_text_switch_and_version_at_the_door() -> None:
    runtime = make_runtime(ScriptedProvider([]))
    restricted = "# Contacts\n\nMail someone@example.com\n"
    with pytest.raises(Error) as caught:
        await run_ingest(
            ingest_request(text=restricted, content_hash=sha(restricted)), runtime, "r"
        )
    assert caught.value.details[0].code == "document_restricted"
    off = make_runtime(
        ScriptedProvider([]), make_settings(capability_documents=CapabilitySettings(enabled=False))
    )
    with pytest.raises(Error) as disabled:
        await run_ingest(ingest_request(), off, "r")
    assert disabled.value.code is ErrorCode.CAPABILITY_DISABLED
    with pytest.raises(Error) as version:
        await run_ingest(ingest_request(capability_version="2.0.0"), runtime, "r")
    assert version.value.code is ErrorCode.CONTRACT_VERSION_MISMATCH
