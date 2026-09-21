"""Properties of the PDF parser: any bytes end in blocks or a reason class, never a crash."""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from catalyst_ai.retrieval.parsers.pdf import parse_pdf
from catalyst_ai.retrieval.parsers.port import Parsed, ParserError

SLOW = [HealthCheck.too_slow]


def _outcome(payload: bytes) -> Parsed | str:
    try:
        return parse_pdf(payload)
    except ParserError as error:
        return "refused" if error.reason.value.startswith("document_") else "unknown"


pdfish = st.one_of(
    st.binary(max_size=300), st.binary(max_size=300).map(lambda b: b"%PDF-1.4\n" + b)
)


@settings(max_examples=60, suppress_health_check=SLOW, deadline=None)
@given(pdfish)
def test_arbitrary_bytes_never_crash(payload: bytes) -> None:
    outcome = _outcome(payload)
    if isinstance(outcome, Parsed):
        assert all(b.heading_path[0].startswith("Page ") for b in outcome.blocks)
    else:
        assert outcome == "refused"
