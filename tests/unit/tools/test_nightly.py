"""The nightly's row in the allowlist, and the property tests' counts under its profile."""

import shutil
from pathlib import Path

import pytest

from tests.conftest import NIGHTLY_FACTOR, examples
from tools import rules
from tools.checks import ci

COMMITTED = rules.NIGHTLY_WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A tree holding copies of every committed workflow."""
    for workflow in (rules.WORKFLOW, rules.CI_IMAGE_WORKFLOW, rules.NIGHTLY_WORKFLOW):
        (tmp_path / workflow).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workflow, tmp_path / workflow)
    return tmp_path


def _plant(root: Path, old: str, new: str) -> list[str]:
    assert old in COMMITTED, f"the plant anchor {old!r} is not in the nightly"
    (root / rules.NIGHTLY_WORKFLOW).write_text(COMMITTED.replace(old, new, 1), encoding="utf-8")
    return [v.message for v in ci.run(root)]


def test_every_committed_workflow_passes(root: Path) -> None:
    assert ci.run(root) == []


def test_an_unlisted_step_in_the_nightly_is_refused(root: Path) -> None:
    found = _plant(root, "      - run: make nightly\n", "      - run: python -c 'print(1)'\n")
    assert "the nightly runs \"python -c 'print(1)'\", which it may not" in found
    assert "the nightly does not run `make nightly`" in found


def test_a_nightly_on_every_push_is_refused(root: Path) -> None:
    found = _plant(root, '  schedule:\n    - cron: "0 2 * * *"\n', "  push:\n")
    assert any(message.startswith("triggers are not") for message in found)


def test_the_nightly_runs_in_the_same_container_as_the_gate(root: Path) -> None:
    found = _plant(root, "    container:\n", "    container:\n      options: --privileged\n")
    assert any("'container'" in message for message in found)


def test_a_property_test_keeps_its_own_count_outside_the_nightly() -> None:
    assert examples(60) == 60
    assert NIGHTLY_FACTOR > 1


def test_a_scanner_action_in_place_of_make_is_refused(root: Path) -> None:
    found = _plant(
        root, "      - run: make image-scan\n", "      - uses: aquasecurity/trivy-action@master\n"
    )
    assert "the nightly uses aquasecurity/trivy-action@master, which it may not" in found
    assert any("the scan job must set up" in message for message in found)


def test_the_scan_job_is_required_and_its_steps_run_in_order(root: Path) -> None:
    missing = _plant(root, "  image-scan:\n", "  other:\n")
    assert "the nightly must hold the 'image-scan' job" in missing
    swapped = _plant(
        root,
        "      - run: make scan-tools\n      - run: make image-scan\n",
        "      - run: make image-scan\n      - run: make scan-tools\n",
    )
    assert any("the scan job must set up" in message for message in swapped)
