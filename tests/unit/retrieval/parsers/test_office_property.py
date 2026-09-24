"""Properties of the office parsers: any bytes end in blocks or a reason class, never a crash."""

import io
import zipfile
from collections.abc import Callable

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from catalyst_ai.retrieval.parsers.office import parse_docx, parse_pptx
from catalyst_ai.retrieval.parsers.port import Parsed, ParserError
from tests.conftest import examples

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
SLOW = [HealthCheck.too_slow]
words = st.sampled_from(["alpha", "beta", "&amp;", "<w:b/>", "", "é"])


def _outcome(parser: Callable[[bytes], Parsed], payload: bytes) -> Parsed | str:
    try:
        return parser(payload)
    except ParserError as error:
        return "refused" if error.reason.value.startswith("document_") else "unknown"


def _docx(paragraphs: list[str]) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
        )
    return buffer.getvalue()


@settings(max_examples=examples(60), suppress_health_check=SLOW, deadline=None)
@given(st.binary(max_size=400))
def test_arbitrary_bytes_never_crash(payload: bytes) -> None:
    for parser in (parse_docx, parse_pptx):
        outcome = _outcome(parser, payload)
        if isinstance(outcome, Parsed):
            assert all(block.text for block in outcome.blocks)
        else:
            assert outcome == "refused"


@settings(max_examples=examples(60), suppress_health_check=SLOW, deadline=None)
@given(st.lists(words, max_size=8))
def test_well_formed_paragraphs_come_back_in_order(paragraphs: list[str]) -> None:
    parsed = parse_docx(_docx(paragraphs))
    expected = [" ".join(p.replace("&amp;", "&").replace("<w:b/>", "").split()) for p in paragraphs]
    assert [b.text for b in parsed.blocks] == [p for p in expected if p]
