"""RULE-005 §1: one image pinned by digest; both Dockerfiles, the Makefile and workflow agree."""

import hashlib
import re
import subprocess
from pathlib import Path

from tools import ci_image, rules
from tools.checks.gate import Violation

FROM = re.compile(r"^FROM\s+(?P<image>\S+)", re.M | re.I)
MAKE_CI_IMAGE = re.compile(r"^CI_IMAGE\s*:?=\s*(?P<image>\S+)\s*$", re.M)
CONTAINER_IMAGE = re.compile(r"^\s*container:\s*\n\s+image:\s*(?P<image>\S+)", re.M)
UV_PIN = re.compile(r"\buv==(\S+)")
APT_INSTALL = re.compile(r"apt-get install(?P<rest>[^\n]*)")
COPIES = re.compile(r"^\s*(?P<verb>COPY|ADD)\b", re.M | re.I)


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
    """Report a CI image on another base, with another uv, or carrying any file of the tree.

    The image is published; it holds public software only, so no `COPY` or `ADD` may ever put
    the repository, or anything else, into it.
    """
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
    violations += [
        Violation(where, 1, f"{m.group('verb').upper()} puts files into a published image; refused")
        for m in COPIES.finditer(dockerfile_ci)
    ]
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


def _pinned_label() -> str | None:
    """Return the pinned registry image's label when the image is on this machine, else None."""
    if not rules.CI_IMAGE.startswith(rules.CI_REGISTRY):
        return None
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", ci_image.LABEL_FORMAT, rules.CI_IMAGE],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def pin_violations(
    dockerfile_sha: str, pinned_sha: str | None, label: str | None
) -> list[Violation]:
    """Report the pinned registry image and `Dockerfile.ci` no longer being the same thing.

    An edit to the Dockerfile without a digest bump leaves the pin on an image built from the old
    file; a bump without an edit points at an image whose label names another file. The label is
    read only where the image is present; the file's hash is always compared with the pin's.
    """
    where = rules.DOCKERFILE_CI.as_posix()
    if pinned_sha is None:
        return []
    violations = []
    if dockerfile_sha != pinned_sha:
        violations.append(
            Violation(where, 1, "Dockerfile.ci changed without a digest bump in tools/rules.py")
        )
    if label is not None and label != pinned_sha:
        violations.append(
            Violation(where, 1, "the pinned image's label names another Dockerfile.ci than the pin")
        )
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
    sha = hashlib.sha256((root / rules.DOCKERFILE_CI).read_bytes()).hexdigest()
    return (
        check(dockerfile, makefile, workflow)
        + ci_image_violations(dockerfile_ci, uv_version)
        + setup_violations(dockerfile_ci, rules.CI_SETUP)
        + pin_violations(sha, rules.CI_IMAGE_BUILT_FROM, _pinned_label())
    )
