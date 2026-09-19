"""The door: RESTRICTED-looking or hostile values are refused with a reason class, never a value."""

import re
from enum import StrEnum

from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error

MAX_TOTAL_CHARS = 40_000


class ReasonClass(StrEnum):
    """Why an input was refused; the class is returned, the value never is."""

    RESTRICTED_PATTERN = "restricted_pattern"
    CONTROL_SEQUENCE = "control_sequence"
    TOO_LARGE = "too_large"


RESTRICTED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("bearer_like_key", re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9]{20,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("ipv4", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _detail(field: str, reason: ReasonClass, pattern: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=reason.value, message=f"matches {pattern}")


def scan_fields(fields: dict[str, str | None]) -> list[ErrorDetail]:
    """Return one detail per refused field; the details carry the reason, never the text."""
    details: list[ErrorDetail] = []
    total = 0
    for name, value in fields.items():
        if not value:
            continue
        total += len(value)
        if CONTROL.search(value):
            details.append(_detail(name, ReasonClass.CONTROL_SEQUENCE, "control characters"))
            continue
        for label, pattern in RESTRICTED_PATTERNS:
            if pattern.search(value):
                details.append(_detail(name, ReasonClass.RESTRICTED_PATTERN, label))
                break
    if total > MAX_TOTAL_CHARS:
        details.append(_detail("*", ReasonClass.TOO_LARGE, f"total over {MAX_TOTAL_CHARS} chars"))
    return details


def refuse_if_needed(fields: dict[str, str | None]) -> None:
    """Raise the catalog error when any field must be refused."""
    details = scan_fields(fields)
    if not details:
        return
    if all(d.code == ReasonClass.TOO_LARGE for d in details):
        raise Error(ErrorCode.INPUT_TOO_LARGE, "the input is too large", details=details)
    raise Error(ErrorCode.INPUT_REJECTED, "the input was refused at the door", details=details)
