"""The locally built CI image: named by its Dockerfile, refused when missing, the mirror kept out."""

import subprocess
from types import SimpleNamespace

import pytest

from tools import ci_image, ci_steps, rules
from tools.checks import images

DOCKERFILE_CI = (
    f"FROM {rules.BASE_IMAGE}\n"
    "ARG APT_MIRROR=http://deb.debian.org/debian\n"
    "RUN apt-get update && apt-get install -y --no-install-recommends make git curl ca-certificates\n"
    "RUN pip install --no-cache-dir uv==0.12.16\n"
)


def test_the_tag_is_the_dockerfile_and_nothing_else(monkeypatch: pytest.MonkeyPatch) -> None:
    first = ci_image.tag(b"FROM x\n")
    monkeypatch.setenv(ci_image.MIRROR_VARIABLE, "http://mirror.invalid/debian")
    assert ci_image.tag(b"FROM x\n") == first
    assert ci_image.tag(b"FROM y\n") != first
    assert first.startswith("catalyst-ai-ci:")


def test_the_mirror_is_a_build_argument_only_when_this_machine_names_one() -> None:
    plain = ci_image.build_command("catalyst-ai-ci:abc", None)
    assert "--build-arg" not in plain
    mirrored = ci_image.build_command("catalyst-ai-ci:abc", "http://mirror.invalid/debian")
    assert mirrored[mirrored.index("--build-arg") + 1] == "APT_MIRROR=http://mirror.invalid/debian"
    assert mirrored[-3:] == ["-t", "catalyst-ai-ci:abc", "."]


def test_a_missing_image_is_refused_with_the_command_that_builds_it(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = SimpleNamespace(returncode=1, stdout="")
    monkeypatch.setattr(subprocess, "run", lambda *_a, **_k: missing)
    assert ci_image.require() == 1
    assert "make ci-image" in capsys.readouterr().err


def test_the_prebuilt_run_leaves_out_the_setup_step_and_nothing_else() -> None:
    workflow = f"      - run: {rules.CI_SETUP}\n      - run: make tools\n      - run: make verify\n"
    assert ci_steps.local_steps(workflow, prebuilt=False)[0] == rules.CI_SETUP
    assert ci_steps.local_steps(workflow, prebuilt=True) == ["make tools", "make verify"]


def test_the_image_and_the_hosted_setup_step_install_the_same_things() -> None:
    assert images.setup_violations(DOCKERFILE_CI, rules.CI_SETUP) == []


def test_a_package_the_image_lacks_or_another_uv_is_refused() -> None:
    fewer = DOCKERFILE_CI.replace(" curl", "")
    found = [v.message for v in images.setup_violations(fewer, rules.CI_SETUP)]
    assert found == ["the setup step installs ['curl'], which the CI image does not"]
    other_uv = DOCKERFILE_CI.replace("uv==0.12.16", "uv==0.12.15")
    assert images.setup_violations(other_uv, rules.CI_SETUP) != []
