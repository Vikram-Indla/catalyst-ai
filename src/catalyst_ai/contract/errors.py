"""Error codes of the contract, each with its HTTP status and its documented degradation."""

from enum import StrEnum
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field


class ErrorCode(StrEnum):
    """Every code a response may carry; the ledger is generated from this enum."""

    AUTH_INVALID = "auth.token.invalid"
    VALIDATION_INVALID_INPUT = "validation.invalid_input"
    CONTRACT_VERSION_MISMATCH = "ai.contract.version_mismatch"
    CAPABILITY_UNKNOWN = "ai.capability.unknown"
    CAPABILITY_DISABLED = "ai.capability.disabled"
    INPUT_REJECTED = "ai.input.rejected"
    INPUT_TOO_LARGE = "ai.input.too_large"
    BUDGET_EXCEEDED = "ai.budget.exceeded"
    PROVIDER_UNAVAILABLE = "ai.provider.unavailable"
    PROVIDER_TIMEOUT = "ai.provider.timeout"
    PROVIDER_REJECTED = "ai.provider.rejected"
    PROVIDER_QUOTA = "ai.provider.quota"
    OUTPUT_INVALID = "ai.output.invalid"
    OUTPUT_UNSAFE = "ai.output.unsafe"
    INTERNAL_ERROR = "internal.error"


HTTP_STATUS = MappingProxyType(
    {
        ErrorCode.AUTH_INVALID: 401,
        ErrorCode.VALIDATION_INVALID_INPUT: 400,
        ErrorCode.CONTRACT_VERSION_MISMATCH: 400,
        ErrorCode.CAPABILITY_UNKNOWN: 404,
        ErrorCode.CAPABILITY_DISABLED: 503,
        ErrorCode.INPUT_REJECTED: 422,
        ErrorCode.INPUT_TOO_LARGE: 413,
        ErrorCode.BUDGET_EXCEEDED: 429,
        ErrorCode.PROVIDER_UNAVAILABLE: 503,
        ErrorCode.PROVIDER_TIMEOUT: 504,
        ErrorCode.PROVIDER_REJECTED: 422,
        ErrorCode.PROVIDER_QUOTA: 429,
        ErrorCode.OUTPUT_INVALID: 502,
        ErrorCode.OUTPUT_UNSAFE: 502,
        ErrorCode.INTERNAL_ERROR: 500,
    }
)

PLATFORM_CODES = frozenset(
    {
        ErrorCode.AUTH_INVALID,
        ErrorCode.VALIDATION_INVALID_INPUT,
        ErrorCode.CAPABILITY_UNKNOWN,
        ErrorCode.INTERNAL_ERROR,
    }
)


class ErrorDetail(BaseModel):
    """One field-level detail of a validation or rejection error."""

    model_config = ConfigDict(extra="forbid")

    field: str
    code: str
    message: str


class ErrorBody(BaseModel):
    """Return the error object inside the envelope."""

    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    retry_after_ms: int | None = None


class ErrorEnvelope(BaseModel):
    """Return the one error shape every operation returns, including 401, 404, 429 and 500."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorBody
    request_id: str
