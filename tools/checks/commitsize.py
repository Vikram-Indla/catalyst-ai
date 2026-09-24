"""RULE-005 §1 at the commit: one ticket, ≤ 400 hand-written lines, `gen:` generated only.

The staged diff is measured: the added and deleted lines of every path `commits.is_generated`
does not class as generated (a binary file counts nothing). The ticket is read from the
`**Ticket:**` field of every staged session record; two tickets in one commit are refused. With
the commit's message (the `commit-msg` hook), a `gen:` commit holding a hand-written path is
refused too. An exception is the lead's decision and nothing else: a staged record names it
(`**Size exception:** D-NNN`) and `brain/02-DECISIONS.md` holds that row decided by the lead —
not proposed — naming RULE-005. There is no flag that skips this check.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools import rules
from tools.checks.commits import is_generated
from tools.checks.gate import Violation
from tools.checks.gitinfo import git_output

MAX_LINES = 400
BIGGEST = 3
DECISIONS = Path("brain/02-DECISIONS.md")
DECIDED_BY = "lead"
RULE = "RULE-005"
TICKET_FIELD = re.compile(r"\*\*Ticket:\*\*\s*(?P<field>[^·\n]+)")
TICKET = re.compile(r"\bAI-\d{3}\b")
EXCEPTION = re.compile(r"\*\*Size exception:\*\*\s*(?P<id>D-\d{3})\b")
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


def decided(decision: str, decisions: str) -> bool:
    """Whether the decisions log holds this row, decided by the lead and naming RULE-005."""
    for line in decisions.splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) > 4 and cells[1] == decision:
            return cells[3] == DECIDED_BY and RULE in line
    return False


def excepted(records: dict[str, str], decisions: str) -> bool:
    """Whether a staged record names a size exception the lead decided."""
    named = [m.group("id") for text in records.values() for m in EXCEPTION.finditer(text)]
    return any(decided(decision, decisions) for decision in named)


def _over(written: list[Staged]) -> str:
    total = sum(s.lines for s in written)
    biggest = sorted(written, key=lambda s: -s.lines)[:BIGGEST]
    listed = ", ".join(f"{s.path} {s.lines}" for s in biggest)
    return f"{total} hand-written lines, over {MAX_LINES}; the biggest: {listed}"


def check(
    staged: list[Staged], records: dict[str, str], decisions: str, message: str | None = None
) -> list[Violation]:
    """Report a `gen:` commit with hand-written paths, a commit over the lines, two tickets."""
    written = [s for s in staged if not is_generated(s.path)]
    violations = []
    if message is not None and GEN.match(message) and written:
        text = f"a gen: commit holds the hand-written {written[0].path}"
        violations.append(Violation(WHERE, 1, text))
    allowed = excepted(records, decisions)
    if sum(s.lines for s in written) > MAX_LINES and not allowed:
        violations.append(Violation(WHERE, 1, _over(written)))
    found = tickets(records)
    if len(found) > 1 and not allowed:
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


def _decisions(root: Path) -> str:
    path = root / DECISIONS
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def run(root: Path, message: str | None = None) -> list[Violation]:
    """Judge what is staged; with nothing staged there is no commit to judge."""
    staged = staged_lines(root)
    if not staged:
        return []
    return check(staged, staged_records(root, staged), _decisions(root), message)


def main(argv: list[str]) -> int:
    """Judge the staged commit with its message's first line, as the `commit-msg` hook."""
    first = Path(argv[0]).read_text(encoding="utf-8").splitlines()[:1]
    found = run(Path.cwd(), first[0] if first else "")
    for violation in found:
        print(f"commit-msg: {violation.render()}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
