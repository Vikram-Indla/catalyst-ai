"""RULE-005 §1 at the commit: one ticket, one subject line, `gen:` generated only.

A commit is one task: the ticket is read from the `**Ticket:**` field of every staged session
record, and two tickets in one commit are refused. There is no total of lines per commit; a file
still keeps its own size (`tools/checks/filebudget`). With the commit's message (the `commit-msg`
hook), the message must be one subject line and nothing after it, and a `gen:` commit holding a
hand-written path is refused. There is no flag that skips this check.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools import rules
from tools.checks.commits import is_generated
from tools.checks.gate import Violation
from tools.checks.gitinfo import git_output

TICKET_FIELD = re.compile(r"\*\*Ticket:\*\*\s*(?P<field>[^·\n]+)")
TICKET = re.compile(r"\bAI-\d{3}\b")
GEN = re.compile(r"^gen(\([a-z0-9._-]+\))?!?: ")
WHERE = ".git"


@dataclass(frozen=True)
class Staged:
    """One staged path and its changed lines."""

    path: str
    lines: int


def tickets(records: dict[str, str]) -> set[str]:
    """Return every ticket the staged records' `**Ticket:**` fields name."""
    found: set[str] = set()
    for text in records.values():
        field = TICKET_FIELD.search(text)
        if field:
            found.update(TICKET.findall(field.group("field")))
    return found


def subject_lines(message: str) -> list[str]:
    """Return the message's lines as git keeps them: not blank, not a comment."""
    return [line for line in message.splitlines() if line.strip() and not line.startswith("#")]


def _message_violations(staged: list[Staged], message: str) -> list[Violation]:
    violations = []
    lines = subject_lines(message)
    if len(lines) > 1:
        text = f"a commit message is one subject line; this one has {len(lines)} lines"
        violations.append(Violation(WHERE, 1, text))
    written = [s for s in staged if not is_generated(s.path)]
    if lines and GEN.match(lines[0]) and written:
        text = f"a gen: commit holds the hand-written {written[0].path}"
        violations.append(Violation(WHERE, 1, text))
    return violations


def check(
    staged: list[Staged], records: dict[str, str], message: str | None = None
) -> list[Violation]:
    """Report two tickets in one commit and, with the message, a second line or a mixed gen:."""
    violations = [] if message is None else _message_violations(staged, message)
    found = tickets(records)
    if len(found) > 1:
        text = f"{len(found)} tickets in one commit: {', '.join(sorted(found))}"
        violations.append(Violation(WHERE, 1, text))
    return violations


def _count(cell: str) -> int:
    return int(cell) if cell.isdigit() else 0


def staged_lines(root: Path) -> list[Staged]:
    """Return the staged paths with their added and deleted lines."""
    out = git_output(root, "diff", "--cached", "--numstat", "--no-renames") or ""
    rows = [line.split("\t") for line in out.splitlines() if line.count("\t") == 2]
    return [Staged(path, _count(added) + _count(deleted)) for added, deleted, path in rows]


def staged_records(root: Path, staged: list[Staged]) -> dict[str, str]:
    """Return the staged session records as the commit will hold them."""
    prefix = rules.SESSIONS.as_posix() + "/"
    return {
        s.path: git_output(root, "show", f":{s.path}") or ""
        for s in staged
        if s.path.startswith(prefix) and s.path.endswith(".md") and "_TEMPLATE" not in s.path
    }


def run(root: Path, message: str | None = None) -> list[Violation]:
    """Judge what is staged; with nothing staged there is no commit to judge."""
    staged = staged_lines(root)
    if not staged:
        return []
    return check(staged, staged_records(root, staged), message)


def main(argv: list[str]) -> int:
    """Judge the staged commit with its whole message, as the `commit-msg` hook."""
    found = run(Path.cwd(), Path(argv[0]).read_text(encoding="utf-8"))
    for violation in found:
        print(f"commit-msg: {violation.render()}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
