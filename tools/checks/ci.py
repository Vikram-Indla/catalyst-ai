"""RULE-005 §1: one workflow file, and it holds only what the local pipeline runs.

Every file under .github/workflows/ is read against its own row (`ci_image_job` holds the image
workflow's, `nightly_job` the nightly's); any other file is refused. `ci.yml` holds only
checkout, setup, make tools, make hooks and make verify, and its trigger, container, services
and env equal what
tools/rules.py pins — the same values `make ci` starts its own database with, so the hosted run
and the local one reach PostgreSQL through the same door.
"""

import re
from pathlib import Path

import yaml

from tools import rules
from tools.checks import ci_image_job, nightly_job, release_job
from tools.checks.gate import Violation

USES = re.compile(r"^\s*-?\s*uses:\s*(?P<value>\S+)", re.M)
RUN = re.compile(r"^\s*-?\s*run:\s*(?P<value>.+)$", re.M)
TOP_KEYS = frozenset({"name", "on", "jobs"})
JOB_KEYS = frozenset({"runs-on", "container", "services", "env", "steps"})


def expected_job() -> dict[str, object]:
    """Return the job's pinned shape, steps aside."""
    return {
        "runs-on": "ubuntu-latest",
        "container": {"image": rules.CI_IMAGE},
        "services": {
            rules.CI_DATABASE_ALIAS: {
                "image": rules.CI_DATABASE_IMAGE,
                "env": rules.CI_DATABASE_ENV,
                "options": rules.CI_DATABASE_OPTIONS,
            }
        },
        "env": rules.CI_JOB_ENV,
    }


def _step_violations(workflow: str, where: str) -> list[Violation]:
    violations = [
        Violation(where, 1, f"workflow uses {m.group('value')}, which the gate does not")
        for m in USES.finditer(workflow)
        if m.group("value") not in rules.CI_ALLOWED_USES
    ]
    runs = [m.group("value").strip() for m in RUN.finditer(workflow)]
    violations += [
        Violation(where, 1, f"workflow runs {command!r}, which the gate does not")
        for command in runs
        if command not in rules.CI_ALLOWED_RUNS
    ]
    if "make verify" not in runs:
        violations.append(Violation(where, 1, "workflow does not run `make verify`"))
    return violations


def _load(workflow: str) -> dict[object, object] | str:
    """Return the workflow as a mapping (YAML's `on` read back as "on"), or why it is not."""
    try:
        document = yaml.safe_load(workflow)
    except yaml.YAMLError as error:
        return f"workflow is not valid YAML: {error}"
    if not isinstance(document, dict):
        return "workflow is not a mapping"
    return {"on" if key is True else key: value for key, value in document.items()}


def _shape_violations(workflow: str, where: str) -> list[Violation]:
    document = _load(workflow)
    if isinstance(document, str):
        return [Violation(where, 1, document)]
    violations = [
        Violation(where, 1, f"workflow key {key!r} is not allowed")
        for key in document
        if key not in TOP_KEYS
    ]
    if document.get("on") != rules.CI_TRIGGERS:
        violations.append(Violation(where, 1, f"workflow triggers are not {rules.CI_TRIGGERS}"))
    jobs = document.get("jobs")
    if not isinstance(jobs, dict) or set(jobs) != {rules.CI_JOB}:
        return [*violations, Violation(where, 1, f"workflow must hold one job, {rules.CI_JOB!r}")]
    job = jobs[rules.CI_JOB]
    shape = {key: value for key, value in job.items() if key != "steps"}
    violations += [
        Violation(where, 1, f"job key {key!r} is {shape.get(key)!r}, not the pinned {pinned!r}")
        for key, pinned in expected_job().items()
        if shape.get(key) != pinned
    ]
    violations += [
        Violation(where, 1, f"job key {key!r} is not allowed") for key in job if key not in JOB_KEYS
    ]
    return violations


def check(workflow: str, where: str) -> list[Violation]:
    """Report any step outside the allowed set and any departure from the pinned shape."""
    return _step_violations(workflow, where) + _shape_violations(workflow, where)


def _image_violations(workflow: str, where: str) -> list[Violation]:
    document = _load(workflow)
    if isinstance(document, str):
        return [Violation(where, 1, document)]
    return ci_image_job.check(document, workflow, where)


def _release_violations(workflow: str, where: str) -> list[Violation]:
    document = _load(workflow)
    if isinstance(document, str):
        return [Violation(where, 1, document)]
    return release_job.check(document, workflow, where)


def _nightly_violations(workflow: str, where: str) -> list[Violation]:
    document = _load(workflow)
    if isinstance(document, str):
        return [Violation(where, 1, document)]
    return nightly_job.check(document, workflow, where, expected_job())


def run(root: Path) -> list[Violation]:
    """Read every file in the workflow directory, each against its own row of the allowlist."""
    directory = root / rules.WORKFLOWS
    present = sorted(p for p in directory.iterdir() if p.is_file()) if directory.is_dir() else []
    allowed = {
        rules.WORKFLOW.name,
        rules.CI_IMAGE_WORKFLOW.name,
        rules.NIGHTLY_WORKFLOW.name,
        rules.RELEASE_WORKFLOW.name,
    }
    violations = [
        Violation(p.relative_to(root).as_posix(), 1, "a workflow the gate does not hold")
        for p in present
        if p.name not in allowed
    ]
    for row, rule in (
        (rules.CI_IMAGE_WORKFLOW, _image_violations),
        (rules.NIGHTLY_WORKFLOW, _nightly_violations),
        (rules.RELEASE_WORKFLOW, _release_violations),
    ):
        if (root / row).exists():
            violations += rule((root / row).read_text(encoding="utf-8"), row.as_posix())
    path = root / rules.WORKFLOW
    if not path.exists():
        return [*violations, Violation(rules.WORKFLOW.as_posix(), 1, "no workflow file")]
    return violations + check(path.read_text(encoding="utf-8"), rules.WORKFLOW.as_posix())
