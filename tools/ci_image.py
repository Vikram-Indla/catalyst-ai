"""The pipeline's image, built on this machine: named by what defines it, never by where apt read.

`make ci` runs in `catalyst-ai-ci:<hash>`, the hash of `Dockerfile.ci` (which carries the base
digest, the packages and the uv pin). A missing image is refused with the command that builds it:
the image is built as its own step, never inside a push. The Debian mirror is a build argument
whose default stays upstream; this machine may pass a nearer one through its own environment
(`CATALYST_AI_CI_APT_MIRROR`), and because apt checks the signed index and every package's
hash, the mirror changes where the bytes come from, not which bytes are accepted. It never
changes the tag.

Every build carries the full hash of `Dockerfile.ci` as a label, so a pinned image says which
file it was built from. Only the image workflow pushes (`push` refuses anywhere else), to the
registry under the repository's owner as the runner names it, and prints the digest the next
`build(ci)` commit pins.
"""

import hashlib
import os
import subprocess
import sys
import time

from tools import rules

REPOSITORY = "catalyst-ai-ci"
TAG_LENGTH = 12
MIRROR_VARIABLE = "CATALYST_AI_CI_APT_MIRROR"
BUILD_HINT = "the pipeline's image is not built on this machine; run `make ci-image` first"
LABEL_FORMAT = '{{index .Config.Labels "' + rules.CI_IMAGE_LABEL + '"}}'


def dockerfile_sha(dockerfile: bytes | None = None) -> str:
    """Return the full SHA-256 of `Dockerfile.ci`: what the tag abbreviates and the label holds."""
    content = dockerfile if dockerfile is not None else rules.DOCKERFILE_CI.read_bytes()
    return hashlib.sha256(content).hexdigest()


def tag(dockerfile: bytes | None = None) -> str:
    """Return the image name for this `Dockerfile.ci`: the same bytes, the same tag."""
    return f"{REPOSITORY}:{dockerfile_sha(dockerfile)[:TAG_LENGTH]}"


def present(image: str) -> bool:
    """Whether the image exists locally."""
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    return completed.returncode == 0


def build_command(image: str, mirror: str | None, sha: str | None = None) -> list[str]:
    """Return the build: labelled with the Dockerfile's hash; a mirror only if one is named."""
    label = f"{rules.CI_IMAGE_LABEL}={sha or dockerfile_sha()}"
    command = ["docker", "build", "--progress=plain", "-f", rules.DOCKERFILE_CI.as_posix()]
    command += ["--label", label]
    if mirror:
        command += ["--build-arg", f"APT_MIRROR={mirror}"]
    return [*command, "-t", image, "."]


def require() -> int:
    """Refuse, with the command that fixes it, when the image for this Dockerfile is missing."""
    image = tag()
    if present(image):
        print(image)
        return 0
    print(f"ci: {BUILD_HINT} ({image})", file=sys.stderr)
    return 1


def build() -> int:
    """Build the image and time it; say which mirror apt read from, not what it is called."""
    image = tag()
    mirror = os.environ.get(MIRROR_VARIABLE) or None
    source = "this machine's mirror" if mirror else "the upstream default"
    print(f"ci-image: building {image} with {source}")
    started = time.monotonic()
    completed = subprocess.run(build_command(image, mirror), check=False)
    elapsed = time.monotonic() - started
    print(f"ci-image: exit {completed.returncode} in {elapsed:.0f} s ({source})")
    return completed.returncode


def _docker(*args: str, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], input=stdin, capture_output=True, check=False, encoding="utf-8"
    )


def remote(owner: str, image: str) -> str:
    """Return the registry name for a local image: the owner lower-cased, the tag kept."""
    return f"{rules.CI_REGISTRY}/{owner.lower()}/{image}"


def push() -> int:
    """From the image workflow only: check the label, push, and print the digest to pin."""
    if os.environ.get("GITHUB_ACTIONS") != "true":
        print("ci-image-push: only the image workflow pushes", file=sys.stderr)
        return 1
    image = tag()
    label = _docker("image", "inspect", "--format", LABEL_FORMAT, image).stdout.strip()
    if label != dockerfile_sha():
        print(f"ci-image-push: {image} was not built from this Dockerfile.ci", file=sys.stderr)
        return 1
    return _publish(image, remote(os.environ["GITHUB_REPOSITORY_OWNER"], image), label)


def _publish(image: str, target: str, label: str) -> int:
    """Log in with the job's token, then tag, then push, each only after the one before worked."""
    actor, token = os.environ["GITHUB_ACTOR"], os.environ["GITHUB_TOKEN"]
    steps = (
        ("login", rules.CI_REGISTRY, "-u", actor, "--password-stdin"),
        ("tag", image, target),
        ("push", target),
    )
    for args in steps:
        completed = _docker(*args, stdin=token if args[0] == "login" else None)
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
            return completed.returncode
    digest = _docker("image", "inspect", "--format", "{{index .RepoDigests 0}}", target)
    print(f"ci-image-push: pushed {digest.stdout.strip()} (label {label[:TAG_LENGTH]})")
    return 0


def main(argv: list[str]) -> int:
    """`tag`, `require` or `build`."""
    command = argv[0] if argv else "tag"
    if command == "tag":
        print(tag())
        return 0
    return {"require": require, "build": build, "push": push}[command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
