"""The completion is untrusted: foreign identifiers, secrets and unrequested links never leave."""

import logging
import re

from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.safety.input import RESTRICTED_PATTERNS

ITEM_KEY = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b")
URL = re.compile(r"https?://[^\s)>\]]+")
FENCE_MARKER = re.compile(r"<<<[^<>]{0,64}>>>")
INJECTION_PHRASE = re.compile(r"\bignore (?:all |the )?previous instructions\b", re.I)
log = logging.getLogger(__name__)


def _known(pattern: re.Pattern[str], texts: list[str]) -> set[str]:
    found: set[str] = set()
    for text in texts:
        found.update(pattern.findall(text))
    return found


def scan_output(completion: str, request_texts: list[str]) -> list[ErrorDetail]:
    """Return one detail per class of leak; the completion itself is never in a detail."""
    details: list[ErrorDetail] = []
    known_keys = _known(ITEM_KEY, request_texts)
    known_urls = _known(URL, request_texts)
    foreign_keys = set(ITEM_KEY.findall(completion)) - known_keys
    if foreign_keys:
        details.append(
            ErrorDetail(
                field="completion",
                code="foreign_identifier",
                message="an item key the request did not carry",
            )
        )
    if set(URL.findall(completion)) - known_urls:
        details.append(
            ErrorDetail(
                field="completion",
                code="unrequested_url",
                message="a link the request did not carry",
            )
        )
    for label, pattern in RESTRICTED_PATTERNS:
        if label != "ipv4" and pattern.search(completion):
            details.append(
                ErrorDetail(field="completion", code="secret_pattern", message=f"matches {label}")
            )
            break
    phrase_in_request = any(INJECTION_PHRASE.search(text) for text in request_texts)
    if FENCE_MARKER.search(completion) or (
        INJECTION_PHRASE.search(completion) and not phrase_in_request
    ):
        details.append(
            ErrorDetail(
                field="completion",
                code="instruction_leak",
                message="fence or injection phrase echoed",
            )
        )
    return details


def refuse_if_unsafe(completion: str, request_texts: list[str], request_id: str) -> None:
    """Raise `ai.output.unsafe` and log a content-free security event when the scan finds a leak."""
    details = scan_output(completion, request_texts)
    if not details:
        return
    log.warning(
        "output refused by the leakage scanner",
        extra={"request_id": request_id, "reasons": [d.code for d in details], "event": "security"},
    )
    raise Error(ErrorCode.OUTPUT_UNSAFE, "the completion failed the leakage scan", details=details)
