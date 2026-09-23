"""The workflow check walks every workflow file and reads its services, container and env."""

import shlex
import shutil
from pathlib import Path

import pytest
import yaml

from tools import ci_postgres, rules
from tools.checks import ci

COMMITTED = rules.WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A tree holding a copy of the committed workflow and nothing else."""
    (tmp_path / rules.WORKFLOW).parent.mkdir(parents=True)
    shutil.copyfile(rules.WORKFLOW, tmp_path / rules.WORKFLOW)
    return tmp_path


def _plant(root: Path, old: str, new: str) -> None:
    assert old in COMMITTED, f"the plant anchor {old!r} is not in the workflow"
    (root / rules.WORKFLOW).write_text(COMMITTED.replace(old, new, 1), encoding="utf-8")


def test_the_committed_workflow_passes(root: Path) -> None:
    assert ci.run(root) == []


def test_a_second_workflow_file_is_refused(root: Path) -> None:
    second = root / ".github" / "workflows" / "nightly.yaml"
    second.write_text("on: push\njobs:\n  x:\n    runs-on: ubuntu-latest\n", encoding="utf-8")
    found = ci.run(root)
    assert any("nightly.yaml" in v.path for v in found), f"a second workflow passed: {found}"


def test_a_changed_service_image_is_refused(root: Path) -> None:
    _plant(root, "image: pgvector/pgvector", "image: postgres:17 # pgvector/pgvector")
    assert ci.run(root), "a changed service image passed"


def test_a_changed_service_env_is_refused(root: Path) -> None:
    _plant(root, "POSTGRES_DB: catalyst_ai", "POSTGRES_DB: other")
    assert ci.run(root), "a changed service environment passed"


def test_a_second_service_is_refused(root: Path) -> None:
    _plant(root, "    services:\n", "    services:\n      redis:\n        image: redis:7\n")
    assert ci.run(root), "a second service passed"


def test_a_changed_job_env_is_refused(root: Path) -> None:
    _plant(root, "\n    env:\n", "\n    env:\n      EXTRA: '1'\n")
    assert ci.run(root), "an extra job variable passed"


def test_the_local_database_starts_as_the_workflow_declares_its_service() -> None:
    job = yaml.safe_load(COMMITTED)["jobs"][rules.CI_JOB]
    service = job["services"][rules.CI_DATABASE_ALIAS]
    started = ci_postgres.run_args()
    assert started[-1] == service["image"]
    assert f"--network-alias={rules.CI_DATABASE_ALIAS}" in started
    for key, value in service["env"].items():
        assert f"--env={key}={value}" in started
    options = shlex.split(service["options"])
    first = started.index(options[0])
    assert started[first : first + len(options)] == options
    assert ci_postgres.job_args()[1:] == [f"--env={k}={v}" for k, v in job["env"].items()]


def test_a_malformed_workflow_is_reported_not_raised(root: Path) -> None:
    (root / rules.WORKFLOW).write_text("jobs: [unclosed\n", encoding="utf-8")
    assert any("not valid YAML" in v.message for v in ci.run(root))


def test_a_trigger_beyond_main_is_refused(root: Path) -> None:
    _plant(root, "on:\n", "on:\n  pull_request:\n")
    assert ci.run(root), "a pull-request trigger passed"
