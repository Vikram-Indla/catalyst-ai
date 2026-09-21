"""The structural rules a proposed scheme must satisfy before the backend ever sees it."""

from collections import deque
from collections.abc import Sequence

from catalyst_ai.contract.errors import ErrorDetail
from catalyst_ai.contract.propose_workflow import (
    ProposeWorkflowRequest,
    StatusBase,
    StatusCategory,
    TransitionBase,
    TransitionKind,
)

DUPLICATE_STATUS = "workflow_duplicate_status"
NO_INITIAL = "workflow_no_initial"
NO_TERMINAL = "workflow_no_terminal"
CATEGORY_NOT_ALLOWED = "workflow_category_not_allowed"
ENDPOINT_UNKNOWN = "workflow_endpoint_unknown"
SELF_LOOP = "workflow_self_loop"
UNREACHABLE_STATUS = "workflow_unreachable_status"
GUARD_UNKNOWN = "workflow_guard_unknown"
REASON_MISSING = "workflow_reason_missing"
EXISTING_DROPPED = "workflow_existing_dropped"
REASON_KINDS = frozenset({TransitionKind.BACKWARD, TransitionKind.REJECT, TransitionKind.REOPEN})


def _detail(field: str, code: str, message: str) -> ErrorDetail:
    return ErrorDetail(field=field, code=code, message=message)


def initial_of(statuses: Sequence[StatusBase]) -> StatusBase | None:
    """Return the one initial status, or None when there is not exactly one in `todo`."""
    initials = [s for s in statuses if s.initial]
    if len(initials) != 1 or initials[0].category is not StatusCategory.TODO:
        return None
    return initials[0]


def reachable_from(start: str, keys: set[str], transitions: Sequence[TransitionBase]) -> set[str]:
    """Return every status a walk from `start` reaches; a null `from_key` leaves every status."""
    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for transition in transitions:
            leaves_current = transition.from_key is None or transition.from_key == current
            if leaves_current and transition.to_key in keys and transition.to_key not in seen:
                seen.add(transition.to_key)
                queue.append(transition.to_key)
    return seen


def status_details(
    statuses: Sequence[StatusBase], request: ProposeWorkflowRequest
) -> list[ErrorDetail]:
    """Duplicates, the single initial, at least one terminal in `done`, allowed categories."""
    details: list[ErrorDetail] = []
    keys = [s.key for s in statuses]
    for key in sorted({k for k in keys if keys.count(k) > 1}):
        details.append(_detail("statuses", DUPLICATE_STATUS, key))
    if initial_of(statuses) is None:
        details.append(_detail("statuses", NO_INITIAL, "exactly one initial status in todo"))
    if not any(s.terminal and s.category is StatusCategory.DONE for s in statuses):
        details.append(_detail("statuses", NO_TERMINAL, "at least one terminal status in done"))
    allowed = set(request.allowed_categories)
    for status in statuses:
        if status.category not in allowed:
            details.append(_detail("statuses", CATEGORY_NOT_ALLOWED, status.key))
    if request.existing is not None:
        for dropped in sorted({s.key for s in request.existing.statuses} - set(keys)):
            details.append(_detail("statuses", EXISTING_DROPPED, dropped))
    return details


def transition_details(
    statuses: Sequence[StatusBase],
    transitions: Sequence[TransitionBase],
    request: ProposeWorkflowRequest,
) -> list[ErrorDetail]:
    """Endpoints exist, no self-loop, guards from the vocabulary, reasons where kinds need them."""
    details: list[ErrorDetail] = []
    keys = {s.key for s in statuses}
    vocabulary = set(request.guard_vocabulary)
    for index, transition in enumerate(transitions):
        field = f"transitions.{index}"
        for endpoint in (transition.from_key, transition.to_key):
            if endpoint is not None and endpoint not in keys:
                details.append(_detail(field, ENDPOINT_UNKNOWN, endpoint))
        if transition.from_key == transition.to_key:
            details.append(_detail(field, SELF_LOOP, transition.to_key))
        for guard in transition.guards:
            if guard not in vocabulary:
                details.append(_detail(field, GUARD_UNKNOWN, guard))
        if transition.kind in REASON_KINDS and transition.reason_code is None:
            details.append(_detail(field, REASON_MISSING, transition.kind.value))
    return details


def reachability_details(
    statuses: Sequence[StatusBase], transitions: Sequence[TransitionBase]
) -> list[ErrorDetail]:
    """Every status is reached from the initial one; nothing to say without a single initial."""
    initial = initial_of(statuses)
    if initial is None:
        return []
    keys = {s.key for s in statuses}
    reached = reachable_from(initial.key, keys, transitions)
    return [_detail("statuses", UNREACHABLE_STATUS, key) for key in sorted(keys - reached)]


def check_scheme(
    statuses: Sequence[StatusBase],
    transitions: Sequence[TransitionBase],
    request: ProposeWorkflowRequest,
) -> list[ErrorDetail]:
    """Return every structural problem of a proposal; empty means the backend may read it."""
    return (
        status_details(statuses, request)
        + transition_details(statuses, transitions, request)
        + reachability_details(statuses, transitions)
    )
