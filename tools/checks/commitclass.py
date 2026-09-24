"""RULE-005 §6 at the commit: a record tells the truth about the change it is committed with.

The branch is judged by its highest claim (`prclass`); here each record is judged by its own
change. When files are staged — the pre-commit hook, one proposal at a time — every staged session
record must claim a blast radius, and at least the one the staged files derive. With nothing
staged (a full gate over the working tree) there is no commit to judge, and the check passes.
"""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation
from tools.checks.gitinfo import git_output
from tools.checks.prclass import CLAIM, derive

NO_CLAIM = "a committed record claims no blast radius"


def check(staged: list[str], records: dict[str, str]) -> list[Violation]:
    """Report a staged record with no claim, or a claim below its commit's derived radius."""
    derived = derive(staged)
    violations = []
    for path, text in sorted(records.items()):
        match = CLAIM.search(text)
        claimed = match.group("radius") if match else None
        if claimed not in rules.RADII:
            violations.append(Violation(path, 1, NO_CLAIM))
        elif rules.RADII.index(claimed) < rules.RADII.index(derived):
            message = f"claims {claimed} but the files committed with it derive {derived}"
            violations.append(Violation(path, 1, message))
    return violations


def run(root: Path) -> list[Violation]:
    """Read the staged files and the staged session records, as the commit will hold them."""
    staged = [p for p in (git_output(root, "diff", "--cached", "--name-only") or "").split() if p]
    prefix = rules.SESSIONS.as_posix() + "/"
    records = {
        path: git_output(root, "show", f":{path}") or ""
        for path in staged
        if path.startswith(prefix) and path.endswith(".md") and "_TEMPLATE" not in path
    }
    return check(staged, records) if staged else []
