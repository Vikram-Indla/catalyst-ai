"""The nightly workflow: its own row in the per-file allowlist the workflow check walks.

`nightly.yml` is extra evidence, never the push gate: it runs on a schedule (or by hand) and holds
two jobs. The first runs in the same container and against the same database service as `ci.yml`,
and every step after the pinned setup line is a `make` target a workstation runs verbatim. The
second scans the runtime image on the runner itself, which has Docker: the same setup line as the
image workflow, `make tools`, `make scan-tools`, `make image-scan`, in that order, with the pinned
scanner `make` verifies, never a scanner action.
"""

from tools import rules
from tools.checks.gate import Violation
from tools.checks.workflow_rows import job_violations, runs, step_violations

JOB_KEYS = frozenset({"runs-on", "container", "services", "env", "steps"})
SCAN_KEYS = frozenset({"runs-on", "steps"})
SCAN_SHAPE: dict[str, object] = {"runs-on": "ubuntu-latest"}
WHAT = "the nightly"


def _scan_runs(job: object) -> list[str]:
    steps = job.get("steps") if isinstance(job, dict) else None
    listed = steps if isinstance(steps, list) else []
    return [str(step["run"]).strip() for step in listed if isinstance(step, dict) and "run" in step]


def scan_violations(jobs: dict[object, object], where: str) -> list[Violation]:
    """Report the scan job missing, off its shape, or not setting up, installing, then scanning."""
    job = jobs.get(rules.NIGHTLY_SCAN_JOB)
    if not isinstance(job, dict):
        return [Violation(where, 1, f"the nightly must hold the {rules.NIGHTLY_SCAN_JOB!r} job")]
    only_scan: dict[object, object] = {"on": {}, "jobs": {rules.NIGHTLY_SCAN_JOB: job}}
    no_triggers: dict[str, object] = {}
    row = (no_triggers, rules.NIGHTLY_SCAN_JOB, SCAN_SHAPE, SCAN_KEYS)
    violations = job_violations(only_scan, where, row)
    if _scan_runs(job) != list(rules.NIGHTLY_SCAN_RUNS):
        message = "the scan job must set up, then run tools, scan-tools and image-scan, in order"
        violations.append(Violation(where, 1, message))
    return violations


def check(
    document: dict[object, object], workflow: str, where: str, job_shape: dict[str, object]
) -> list[Violation]:
    """Report the nightly departing from its schedule, either job's shape or its steps."""
    allowed = (*rules.NIGHTLY_ALLOWED_RUNS, *rules.NIGHTLY_SCAN_RUNS)
    violations = step_violations(workflow, where, allowed, WHAT)
    if "make nightly" not in runs(workflow):
        violations.append(Violation(where, 1, "the nightly does not run `make nightly`"))
    jobs = document.get("jobs")
    jobs = jobs if isinstance(jobs, dict) else {}
    expected = {rules.NIGHTLY_JOB, rules.NIGHTLY_SCAN_JOB}
    if set(jobs) != expected:
        violations.append(Violation(where, 1, f"must hold the jobs {sorted(expected)}"))
    nightly: dict[object, object] = {
        "on": document.get("on"),
        "jobs": {rules.NIGHTLY_JOB: jobs.get(rules.NIGHTLY_JOB)},
    }
    row = (rules.NIGHTLY_TRIGGERS, rules.NIGHTLY_JOB, job_shape, JOB_KEYS)
    return violations + job_violations(nightly, where, row) + scan_violations(jobs, where)
