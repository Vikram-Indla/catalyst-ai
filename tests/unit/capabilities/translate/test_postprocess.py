"""Stage 7: the confidence penalties and the response fields."""

from catalyst_ai.capabilities.translate.postprocess import confidence
from tests.unit.capabilities.translate.conftest import FIELD, FIELD_AR, make_request


def test_confidence_penalises_script_structure_spans_and_length() -> None:
    request = make_request()
    assert confidence(request, FIELD_AR, "ar") == 1.0
    assert confidence(request, FIELD, "ar") == 0.6
    assert confidence(request, FIELD_AR.replace("- ", ""), "ar") == 0.8
    assert confidence(request, FIELD_AR.replace("PRJ-42", "PRJ-1"), "ar") == 0.7
    assert confidence(request, "قصير", "ar") == 0.4
    assert confidence(make_request(mode="title"), FIELD, "ar") == 0.6
