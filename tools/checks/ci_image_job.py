"""The image workflow: its own row in the per-file allowlist the workflow check walks.

`ci-image.yml` builds `Dockerfile.ci`, runs the gate inside the new image, and only then pushes
it. It runs on a push to `main` that changes `Dockerfile.ci` and nothing else, holds
`packages: write` in its one job, and each step is a `make` target a workstation can run, after
the one pinned setup line that puts uv on the runner.
"""

from tools import rules
from tools.checks.gate import Violation
from tools.checks.workflow_rows import job_violations, runs, step_violations

JOB_KEYS = frozenset({"runs-on", "permissions", "env", "steps"})
WHAT = "the image workflow"


def expected_job() -> dict[str, object]:
    """Return the image job's pinned shape, steps aside."""
    return {
        "runs-on": "ubuntu-latest",
        "permissions": rules.CI_IMAGE_PERMISSIONS,
        "env": rules.CI_IMAGE_JOB_ENV,
    }


def check(document: dict[object, object], workflow: str, where: str) -> list[Violation]:
    """Report the image workflow departing from its trigger, its one job or its steps in order."""
    violations = step_violations(workflow, where, rules.CI_IMAGE_ALLOWED_RUNS, WHAT)
    ordered = [command for command in runs(workflow) if command in rules.CI_IMAGE_ALLOWED_RUNS]
    if ordered != list(rules.CI_IMAGE_ALLOWED_RUNS):
        violations.append(
            Violation(where, 1, "the image workflow must set up, build, gate, then push, in order")
        )
    row = (rules.CI_IMAGE_TRIGGERS, rules.CI_IMAGE_JOB, expected_job(), JOB_KEYS)
    return violations + job_violations(document, where, row)
