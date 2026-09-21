"""PDF parsing over the fixtures: the text layer per page, scripts and loops refused."""

import pytest

from catalyst_ai.retrieval.parsers import Reason
from catalyst_ai.retrieval.parsers.pdf import MAX_BYTES, guard, parse_pdf
from catalyst_ai.retrieval.parsers.port import ParserError
from tests.conftest import REPO_ROOT

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "documents"


def test_pages_become_headings() -> None:
    parsed = parse_pdf((FIXTURES / "benign" / "simple.pdf").read_bytes())
    assert [(b.heading_path, b.text) for b in parsed.blocks] == [
        (("Page 1",), "Incident response runbook"),
        (("Page 2",), "Page two: escalation path"),
    ]


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("script.pdf", Reason.MALFORMED),
        ("loop.pdf", Reason.MALFORMED),
        ("notpdf.pdf", Reason.MALFORMED),
    ],
)
def test_hostile_pdfs_are_refused(name: str, reason: Reason) -> None:
    with pytest.raises(ParserError) as caught:
        parse_pdf((FIXTURES / "hostile" / name).read_bytes())
    assert caught.value.reason is reason


def test_guard_refuses_oversized_before_reading() -> None:
    with pytest.raises(ParserError) as caught:
        guard(b"%PDF-" + b"0" * MAX_BYTES)
    assert caught.value.reason is Reason.TOO_LARGE
