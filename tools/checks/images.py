"""RULE-005 §1: one image pinned by digest; both Dockerfiles, the Makefile and workflow agree."""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

FROM = re.compile(r"^FROM\s+(?P<image>\S+)", re.M | re.I)
MAKE_CI_IMAGE = re.compile(r"^CI_IMAGE\s*:?=\s*(?P<image>\S+)\s*$", re.M)
CONTAINER_IMAGE = re.compile(r"^\s*container:\s*\n\s+image:\s*(?P<image>\S+)", re.M)
UV_PIN = re.compile(r"\buv==(\S+)")
APT_INSTALL = re.compile(r"apt-get install(?P<rest>[^\n]*)")


def _held_to(
    found: list[str], expected: str, where: str, what: str, *, single: bool = False
) -> list[Violation]:
    if not found or (single and len(found) != 1):
        return [Violation(where, 1, f"{what}: expected one image reference, found {len(found)}")]
    return [
        Violation(where, 1, f"{what} is {image}, not the pinned {expected}")
        for image in found
        if image != expected
    ]


def check(dockerfile: str, makefile: str, workflow: str) -> list[Violation]:
    """Report every image reference that is not the one pinned in `tools/rules.py`."""
    return (
        _held_to(
            [m.group("image") for m in FROM.finditer(dockerfile)],
            rules.BASE_IMAGE,
            rules.DOCKERFILE.as_posix(),
            "a FROM line",
        )
        + _held_to(
            [m.group("image") for m in MAKE_CI_IMAGE.finditer(makefile)],
            rules.CI_IMAGE,
            rules.MAKEFILE.as_posix(),
            "CI_IMAGE",
            single=True,
        )
        + _held_to(
            [m.group("image") for m in CONTAINER_IMAGE.finditer(workflow)],
            rules.CI_IMAGE,
            rules.WORKFLOW.as_posix(),
            "the job's container image",
            single=True,
        )
    )


def ci_image_violations(dockerfile_ci: str, uv_version: str) -> list[Violation]:
    """Report a CI image built on another base, or with a uv other than the pinned one."""
    where = rules.DOCKERFILE_CI.as_posix()
    violations = _held_to(
        [m.group("image") for m in FROM.finditer(dockerfile_ci)],
        rules.BASE_IMAGE,
        where,
        "the CI image's FROM line",
        single=True,
    )
    baked = UV_PIN.findall(dockerfile_ci)
    if baked != [uv_version]:
        violations.append(Violation(where, 1, f"bakes uv {baked}, not the pinned {uv_version}"))
    return violations


def _apt_packages(text: str) -> set[str]:
    """Return the packages an `apt-get install` line names, flags left out."""
    found: set[str] = set()
    for match in APT_INSTALL.finditer(text):
        words = match.group("rest").split("&&", maxsplit=1)[0].split()
        found |= {word for word in words if not word.startswith("-") and word != "\\"}
    return found


def setup_violations(dockerfile_ci: str, setup: str) -> list[Violation]:
    """Report the hosted setup step and the CI image disagreeing on a package or on uv.

    The hosted job installs on its runner what the local image carries baked in; the two sides
    run the same gate only while they install the same things.
    """
    where = rules.DOCKERFILE_CI.as_posix()
    violations = []
    image, hosted = _apt_packages(dockerfile_ci), _apt_packages(setup)
    if hosted - image:
        missing = sorted(hosted - image)
        violations.append(
            Violation(where, 1, f"the setup step installs {missing}, which the CI image does not")
        )
    if image - hosted:
        extra = sorted(image - hosted)
        violations.append(
            Violation(where, 1, f"the CI image installs {extra}, which the setup step does not")
        )
    if UV_PIN.findall(dockerfile_ci) != UV_PIN.findall(setup):
        violations.append(Violation(where, 1, "the CI image and the setup step pin different uv"))
    return violations


def run(root: Path) -> list[Violation]:
    """Read the committed files the images are named in."""
    paths = (rules.DOCKERFILE, rules.MAKEFILE, rules.WORKFLOW, rules.DOCKERFILE_CI)
    missing = [p for p in paths if not (root / p).exists()]
    if missing:
        return [Violation(p.as_posix(), 1, "file missing") for p in missing]
    dockerfile, makefile, workflow, dockerfile_ci = (
        (root / p).read_text(encoding="utf-8") for p in paths
    )
    uv_version = dict(
        line.split() for line in (root / ".tool-versions").read_text(encoding="utf-8").splitlines()
    )["uv"]
    return (
        check(dockerfile, makefile, workflow)
        + ci_image_violations(dockerfile_ci, uv_version)
        + setup_violations(dockerfile_ci, rules.CI_SETUP)
    )
