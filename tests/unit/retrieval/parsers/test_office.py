"""Word and PowerPoint parsing over the fixtures: structure read, hostile containers refused."""

import io
import zipfile

import pytest

from catalyst_ai.retrieval.parsers import Reason, parse
from catalyst_ai.retrieval.parsers.office import MAX_ENTRIES, open_zip, parse_docx, parse_pptx
from catalyst_ai.retrieval.parsers.port import ParserError
from tests.conftest import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "documents"


def _zip(parts: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    return buffer.getvalue()


def test_docx_headings_become_the_path() -> None:
    parsed = parse_docx((FIXTURES / "benign" / "simple.docx").read_bytes())
    assert [(b.heading_path, b.text) for b in parsed.blocks] == [
        (("Export the board",), "The export writes every visible column to a CSV file."),
        (
            ("Export the board", "Archived items"),
            "Archived items stay out of the export by default.",
        ),
        (
            ("Export the board", "Archived items"),
            "A member without the permission sees no export button.",
        ),
    ]


def test_pptx_slides_become_headings() -> None:
    parsed = parse_pptx((FIXTURES / "benign" / "simple.pptx").read_bytes())
    assert parsed.headings == ["Slide 1: Release plan", "Slide 2: Risks"]
    assert [b.text for b in parsed.blocks][:2] == ["Freeze on Thursday", "Deploy on Sunday"]
    untitled = _zip(
        {
            "ppt/slides/slide1.xml": b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="1" name="x"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:txBody><a:p><a:r><a:t>only text</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
        }
    )
    assert parse_pptx(untitled).blocks[0].heading_path == ("Slide 1",)


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("bomb.docx", Reason.TOO_LARGE),
        ("macro.docx", Reason.MALFORMED),
        ("nested.docx", Reason.TOO_LARGE),
        ("entity.docx", Reason.MALFORMED),
        ("traversal.docx", Reason.MALFORMED),
        ("notzip.docx", Reason.MALFORMED),
    ],
)
def test_hostile_containers_are_refused_with_their_class(name: str, reason: Reason) -> None:
    with pytest.raises(ParserError) as caught:
        parse("docx", (FIXTURES / "hostile" / name).read_bytes())
    assert caught.value.reason is reason


def test_missing_part_and_too_many_entries() -> None:
    with pytest.raises(ParserError) as missing:
        parse_docx(_zip({"other.xml": b"<x/>"}))
    assert missing.value.reason is Reason.MALFORMED
    crowded = _zip({f"e{i}.xml": b"<x/>" for i in range(MAX_ENTRIES + 1)})
    with pytest.raises(ParserError) as many:
        open_zip(crowded)
    assert many.value.reason is Reason.TOO_LARGE
