"""Print the workflow's run steps joined for one shell: what `make ci` executes in the image.

With `--prebuilt` the setup step is left out: the image `make ci-image` builds already carries
what that step installs, and `tools/checks/images` holds the two to the same packages and pins.
"""

import re
import sys
from pathlib import Path

from tools import rules

RUN = re.compile(r"^\s*-?\s*run:\s*(?P<value>.+)$", re.M)


def steps(workflow: str) -> list[str]:
    """Return the run steps of the workflow, in order."""
    return [m.group("value").strip() for m in RUN.finditer(workflow)]


def local_steps(workflow: str, *, prebuilt: bool) -> list[str]:
    """Return the workflow's steps, without the setup step when the image carries it."""
    return [step for step in steps(workflow) if not (prebuilt and step == rules.CI_SETUP)]


def main(argv: list[str]) -> int:
    """Print the steps joined by `&&`."""
    workflow = Path(rules.WORKFLOW).read_text(encoding="utf-8")
    print(" && ".join(local_steps(workflow, prebuilt="--prebuilt" in argv)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
