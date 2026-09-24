"""The pipeline's image, built on this machine: named by what defines it, never by where apt read.

`make ci` runs in `catalyst-ai-ci:<hash>`, the hash of `Dockerfile.ci` (which carries the base
digest, the packages and the uv pin). A missing image is refused with the command that builds it:
the image is built as its own step, never inside a push. The Debian mirror is a build argument
whose default stays upstream; this machine may pass a nearer one through its own environment
(`CATALYST_AI_CI_APT_MIRROR`), and because apt checks the signed index and every package's
hash, the mirror changes where the bytes come from, not which bytes are accepted. It never
changes the tag.
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


def tag(dockerfile: bytes | None = None) -> str:
    """Return the image name for this `Dockerfile.ci`: the same bytes, the same tag."""
    content = dockerfile if dockerfile is not None else rules.DOCKERFILE_CI.read_bytes()
    return f"{REPOSITORY}:{hashlib.sha256(content).hexdigest()[:TAG_LENGTH]}"


def present(image: str) -> bool:
    """Whether the image exists locally."""
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    return completed.returncode == 0


def build_command(image: str, mirror: str | None) -> list[str]:
    """Return the build: the mirror only as a build argument, only when this machine names one."""
    command = ["docker", "build", "--progress=plain", "-f", rules.DOCKERFILE_CI.as_posix()]
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


def main(argv: list[str]) -> int:
    """`tag`, `require` or `build`."""
    command = argv[0] if argv else "tag"
    if command == "tag":
        print(tag())
        return 0
    return {"require": require, "build": build}[command]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
