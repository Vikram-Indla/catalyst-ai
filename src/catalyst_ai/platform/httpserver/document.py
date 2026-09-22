"""The error side of the contract document: one envelope, referenced from every operation."""

from typing import Any

from catalyst_ai.contract.errors import HTTP_STATUS, PLATFORM_CODES, ErrorCode, ErrorEnvelope

SCHEMAS = "#/components/schemas/{model}"
ENVELOPE_REF = "#/components/schemas/ErrorEnvelope"
FRAMEWORK_SCHEMAS = ("HTTPValidationError", "ValidationError")
OK = "2"
DEFAULT = "default"


def _error_response(codes: list[str]) -> dict[str, Any]:
    return {
        "description": "The error envelope; codes: " + ", ".join(sorted(codes)),
        "content": {"application/json": {"schema": {"$ref": ENVELOPE_REF}}},
    }


def _responses_of(operation: dict[str, Any]) -> dict[str, Any]:
    """Return the operation's responses: the success kept, one per error status, one default."""
    responses = {k: v for k, v in operation.get("responses", {}).items() if k.startswith(OK)}
    declared = {ErrorCode(code) for code in operation.get("x-error-codes", [])}
    by_status: dict[str, list[str]] = {}
    for code in sorted(declared | PLATFORM_CODES, key=str):
        by_status.setdefault(str(HTTP_STATUS[code]), []).append(code.value)
    for status, codes in sorted(by_status.items()):
        responses[status] = _error_response(codes)
    responses[DEFAULT] = _error_response([code.value for code in sorted(declared, key=str)])
    return responses


def with_error_responses(document: dict[str, Any]) -> dict[str, Any]:
    """Declare the envelope's schemas and reference them from every operation's error statuses."""
    schemas = document.setdefault("components", {}).setdefault("schemas", {})
    for name in FRAMEWORK_SCHEMAS:
        schemas.pop(name, None)
    envelope = ErrorEnvelope.model_json_schema(ref_template=SCHEMAS)
    schemas.update(envelope.pop("$defs", {}))
    schemas["ErrorEnvelope"] = envelope
    for path_item in document.get("paths", {}).values():
        for operation in path_item.values():
            operation["responses"] = _responses_of(operation)
    return document
