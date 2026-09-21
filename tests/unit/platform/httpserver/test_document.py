"""with_error_responses: the envelope is declared once and referenced from every error status."""

from typing import Any

from catalyst_ai.platform.httpserver import with_error_responses

REF = "#/components/schemas/ErrorEnvelope"


def _document(codes: list[str]) -> dict[str, Any]:
    return {
        "paths": {
            "/v1/x": {
                "post": {
                    "x-error-codes": codes,
                    "responses": {
                        "200": {"description": "ok"},
                        "422": {"$ref": "#/components/schemas/HTTPValidationError"},
                    },
                }
            }
        },
        "components": {"schemas": {"HTTPValidationError": {}, "ValidationError": {}}},
    }


def _ref_of(response: dict[str, Any]) -> str:
    return str(response["content"]["application/json"]["schema"]["$ref"])


def test_envelope_declared_and_framework_schemas_dropped() -> None:
    document = with_error_responses(_document([]))
    schemas = document["components"]["schemas"]
    assert {"ErrorEnvelope", "ErrorBody", "ErrorDetail", "ErrorCode"} <= set(schemas)
    assert "HTTPValidationError" not in schemas
    assert (
        schemas["ErrorEnvelope"]["properties"]["error"]["$ref"] == "#/components/schemas/ErrorBody"
    )


def test_every_error_status_references_the_envelope() -> None:
    codes = ["ai.input.rejected", "ai.budget.exceeded", "ai.provider.quota", "ai.output.invalid"]
    responses = with_error_responses(_document(codes))["paths"]["/v1/x"]["post"]["responses"]
    assert responses["200"] == {"description": "ok"}
    assert {"400", "401", "404", "422", "429", "500", "502", "default"} <= set(responses)
    assert "HTTPValidationError" not in str(responses)
    for status, response in responses.items():
        if status != "200":
            assert _ref_of(response) == REF
    assert "ai.budget.exceeded, ai.provider.quota" in responses["429"]["description"]
    assert "ai.input.rejected" in responses["default"]["description"]


def test_operation_without_codes_keeps_platform_statuses_only() -> None:
    responses = with_error_responses(_document([]))["paths"]["/v1/x"]["post"]["responses"]
    assert set(responses) == {"200", "400", "401", "404", "500", "default"}
