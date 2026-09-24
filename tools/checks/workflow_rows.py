"""What every row of the workflow allowlist checks the same way: its steps, its trigger, its job.

Each workflow file under `.github/workflows/` has its own row (`ci.yml`, `ci-image.yml`,
`nightly.yml`); the rows differ in what they allow, not in how a step or a job is read.
"""

import re

from tools import rules
from tools.checks.gate import Violation

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<value>\S+)", re.M)
RUN = re.compile(r"^\s*-?\s*run:\s*(?P<value>.+)$", re.M)


def runs(workflow: str) -> list[str]:
    """Return the workflow's `run:` commands, in order."""
    return [m.group("value").strip() for m in RUN.finditer(workflow)]


def step_violations(
    workflow: str, where: str, allowed: tuple[str, ...], what: str
) -> list[Violation]:
    """Report an action outside the allowed uses and a command outside the row's allowed runs."""
    violations = [
        Violation(where, 1, f"{what} uses {m.group('value')}, which it may not")
        for m in USES.finditer(workflow)
        if m.group("value") not in rules.CI_ALLOWED_USES
    ]
    return violations + [
        Violation(where, 1, f"{what} runs {command!r}, which it may not")
        for command in runs(workflow)
        if command not in allowed
    ]


def job_violations(
    document: dict[object, object],
    where: str,
    row: tuple[dict[str, object], str, dict[str, object], frozenset[str]],
) -> list[Violation]:
    """Report a trigger, a job name, a pinned job key or an extra job key off the row.

    The row is (the pinned triggers, the one job's name, its pinned keys, the keys it may hold).
    """
    triggers, name, shape, allowed_keys = row
    violations = []
    if document.get("on") != triggers:
        violations.append(Violation(where, 1, f"triggers are not {triggers}"))
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {name} or not isinstance(jobs[name], dict):
        return [*violations, Violation(where, 1, f"must hold one job, {name!r}")]
    job = jobs[name]
    violations += [
        Violation(where, 1, f"job key {key!r} is {job.get(key)!r}, not the pinned {pinned!r}")
        for key, pinned in shape.items()
        if job.get(key) != pinned
    ]
    return violations + [
        Violation(where, 1, f"job key {key!r} is not allowed")
        for key in job
        if key not in allowed_keys
    ]
