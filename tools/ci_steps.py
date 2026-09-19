"""Print the workflow's run steps joined for one shell: what `make ci` executes in the image."""

import re
import sys
from pathlib import Path

from tools import rules

RUN = re.compile(r"^\s*-?\s*run:\s*(?P<value>.+)$", re.M)


def steps(workflow: str) -> list[str]:
    """Return the run steps of the workflow, in order."""
    return [m.group("value").strip() for m in RUN.finditer(workflow)]


def main() -> int:
    """Print the steps joined by `&&`."""
    print(" && ".join(steps(Path(rules.WORKFLOW).read_text(encoding="utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
