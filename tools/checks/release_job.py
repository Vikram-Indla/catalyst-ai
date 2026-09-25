"""The release workflow: its own row in the per-file allowlist the workflow check walks.

`release.yml` runs on every push to `main`, in one job that alone holds `id-token: write` (the
login by workload identity federation, no action), with the release's settings from the
repository's variables and nothing written in the file. Its steps are the pinned setup line and
`make release`, print-only until the lead approves the hosted login.
"""

from tools import rules
from tools.checks.gate import Violation
from tools.checks.workflow_rows import job_violations, runs, step_violations

JOB_KEYS = frozenset({"runs-on", "permissions", "env", "steps"})
WHAT = "the release workflow"


def expected_job() -> dict[str, object]:
    """Return the release job's pinned shape, steps aside."""
    return {
        "runs-on": "ubuntu-latest",
        "permissions": rules.RELEASE_PERMISSIONS,
        "env": rules.RELEASE_JOB_ENV,
    }


def check(document: dict[object, object], workflow: str, where: str) -> list[Violation]:
    """Report the release workflow departing from its trigger, its one job or its steps in order."""
    violations = step_violations(workflow, where, rules.RELEASE_ALLOWED_RUNS, WHAT)
    if runs(workflow) != list(rules.RELEASE_ALLOWED_RUNS):
        violations.append(Violation(where, 1, "the release workflow must set up, then release"))
    row = (rules.RELEASE_TRIGGERS, rules.RELEASE_JOB, expected_job(), JOB_KEYS)
    return violations + job_violations(document, where, row)
