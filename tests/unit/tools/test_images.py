"""One image, by digest: the Dockerfile, the Makefile and the workflow name what the rules pin."""

from pathlib import Path

from tools import rules
from tools.checks import images


def _files(base: str, ci: str, container: str) -> tuple[str, str, str]:
    dockerfile = f"FROM {base} AS builder\nRUN true\n\nFROM {base} AS runtime\n"
    makefile = f"UV ?= uv\nCI_IMAGE := {ci}\nci:\n\tdocker run $(CI_IMAGE)\n"
    workflow = f"jobs:\n  verify:\n    container:\n      image: {container}\n    steps: []\n"
    return dockerfile, makefile, workflow


def test_the_committed_files_name_the_pinned_image() -> None:
    assert images.run(Path()) == []


def test_the_pin_is_a_digest_not_a_tag() -> None:
    assert "@sha256:" in rules.BASE_IMAGE
    assert "@sha256:" in rules.CI_IMAGE


def test_agreeing_files_pass() -> None:
    assert images.check(*_files(rules.BASE_IMAGE, rules.CI_IMAGE, rules.CI_IMAGE)) == []


def test_a_tag_anywhere_is_refused_where_it_is() -> None:
    tag = "python:3.12.14-slim"
    for position in range(3):
        refs = [rules.BASE_IMAGE, rules.CI_IMAGE, rules.CI_IMAGE]
        refs[position] = tag
        found = images.check(*_files(*refs))
        where = (rules.DOCKERFILE, rules.MAKEFILE, rules.WORKFLOW)[position].as_posix()
        assert found, f"a tag in {where} passed"
        assert {v.path for v in found} == {where}


def test_a_missing_or_doubled_reference_is_refused() -> None:
    dockerfile, makefile, workflow = _files(rules.BASE_IMAGE, rules.CI_IMAGE, rules.CI_IMAGE)
    assert images.check("", makefile, workflow)
    assert images.check(dockerfile, makefile + f"CI_IMAGE := {rules.CI_IMAGE}\n", workflow)
    assert images.check(dockerfile, makefile, "jobs: {}\n")


def test_the_ci_image_is_built_on_the_pinned_base_with_the_pinned_uv() -> None:
    good = f"FROM {rules.BASE_IMAGE}\nRUN pip install --no-cache-dir uv==0.12.16\n"
    assert images.ci_image_violations(good, "0.12.16") == []
    assert images.ci_image_violations(good.replace(rules.BASE_IMAGE, "python:3.12"), "0.12.16")
    assert images.ci_image_violations(good, "0.13.0")
    assert images.ci_image_violations(f"FROM {rules.BASE_IMAGE}\n", "0.12.16")
