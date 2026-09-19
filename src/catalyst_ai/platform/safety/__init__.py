"""Injection, leakage and abuse are input problems: the scanners and the fences."""

from catalyst_ai.platform.safety.delimit import fence, strip_markers
from catalyst_ai.platform.safety.input import refuse_if_needed, scan_fields
from catalyst_ai.platform.safety.output import refuse_if_unsafe, scan_output

__all__ = [
    "fence",
    "refuse_if_needed",
    "refuse_if_unsafe",
    "scan_fields",
    "scan_output",
    "strip_markers",
]
