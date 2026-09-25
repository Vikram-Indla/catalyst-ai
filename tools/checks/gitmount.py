"""The gate's image reads git and never writes it (RULE-005, the pipeline).

Every mount of the git common directory into a container is read-only (`:/gitcommon:ro`), and git
runs there with `GIT_OPTIONAL_LOCKS=0`, so no status, diff or log refreshes the index. A step
inside the image that tried to write the repository's config or index fails with a read-only error
instead of changing the real repository.
"""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

MOUNT = re.compile(r":/gitcommon(?P<mode>:ro)?\b")
NO_LOCKS = "GIT_OPTIONAL_LOCKS=0"


def check(text: str, where: str) -> list[Violation]:
    """Report a writable mount of the git common directory, or its runs without the lock switch."""
    found = []
    mounts = 0
    for number, line in enumerate(text.splitlines(), 1):
        for match in MOUNT.finditer(line):
            mounts += 1
            if match.group("mode") is None:
                found.append(
                    Violation(where, number, "the git common directory is mounted writable")
                )
    if mounts and NO_LOCKS not in text:
        found.append(Violation(where, 1, f"git runs in the image without {NO_LOCKS}"))
    return found


def run(root: Path) -> list[Violation]:
    """Read the Makefile, where the image's runs are defined."""
    path = root / rules.MAKEFILE
    return check(path.read_text(encoding="utf-8"), str(rules.MAKEFILE)) if path.is_file() else []
