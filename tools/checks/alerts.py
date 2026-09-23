"""Every alert names a runbook that exists and is about it, and every SLO has its alert.

An alert without a runbook is a page at three in the morning with nothing to read; a runbook
nothing points at rots. The SLO ledger names the alert per objective, so the three files —
`ops/alerts.yaml`, `docs/06-runbooks/`, `docs/04-ledgers/slos.md` — must agree.

The rule worth failing the gate over is one-directional: **no alert without a runbook that
exists and carries a heading naming that alert**, and no alert the SLO ledger never names. A
link that resolves is not enough: two alerts once pointed at a page about a third, and the
operator it pages reads the wrong procedure. The other direction is a report: a runbook
may exist for a procedure nothing alerts on (rotation, a rebuild, the kill switch), and failing
the gate for it once pushed two alerts to point at pages about something else — an operator
paged at two in the morning reading the wrong page is worse than a runbook with no alert.
"""

import re
from pathlib import Path

import yaml

from tools import rules
from tools.checks.gate import Violation

ALERTS = Path("ops") / "alerts.yaml"
RUNBOOKS = Path("docs") / "06-runbooks"
SLOS = Path("docs") / "04-ledgers" / "slos.md"
INDEX = "README.md"
ALERT_NAME = re.compile(r"`?([A-Z][A-Za-z]+)`?")
UNPOINTED = frozenset({"README.md"})


Document = dict[str, object]


def alert_rules(document: object) -> list[Document]:
    """Every rule of every group, skipping anything that is not a mapping."""
    groups = document.get("groups", []) if isinstance(document, dict) else []
    listed = groups if isinstance(groups, list) else []
    rules_of = (group.get("rules", []) for group in listed if isinstance(group, dict))
    return [
        rule
        for group in rules_of
        if isinstance(group, list)
        for rule in group
        if isinstance(rule, dict)
    ]


def _runbook(rule: Document) -> str:
    annotations = rule.get("annotations", {})
    return str(annotations.get("runbook", "")) if isinstance(annotations, dict) else ""


def alert_violations(document: object, runbooks: set[str], where: str) -> list[Violation]:
    """Report an alert without a name, without a runbook, or naming one that does not exist."""
    violations = []
    for rule in alert_rules(document):
        name = str(rule.get("alert", ""))
        runbook = _runbook(rule)
        if not name:
            violations.append(Violation(where, 1, "a rule without an alert name"))
        elif not runbook:
            violations.append(Violation(where, 1, f"{name} names no runbook"))
        elif Path(runbook).name not in runbooks:
            violations.append(Violation(where, 1, f"{name} names {runbook}, which does not exist"))
    return violations


def about_violations(document: object, headings: dict[str, str]) -> list[Violation]:
    """Report an alert whose runbook has no heading naming it: the page is about something else."""
    violations = []
    pairs = {(str(rule.get("alert", "")), Path(_runbook(rule))) for rule in alert_rules(document)}
    for name, runbook in sorted(pairs):
        if name and runbook.name in headings and name not in headings[runbook.name]:
            where = (RUNBOOKS / runbook.name).as_posix()
            violations.append(Violation(where, 1, f"{name} points here; no heading names it"))
    return violations


def headings_of(text: str) -> str:
    """Return the Markdown headings of a runbook, one per line: what the page is about."""
    return "\n".join(line for line in text.splitlines() if line.startswith("#"))


def coverage_violations(document: object, slos: str, runbooks: set[str]) -> list[Violation]:
    """Report an alert the SLO ledger never mentions, and a runbook no alert points at."""
    violations = []
    named = {str(rule.get("alert", "")) for rule in alert_rules(document)}
    for alert in sorted(named - {""}):
        if alert not in slos:
            violations.append(Violation(SLOS.as_posix(), 1, f"{alert} is in no SLO row"))
    pointed = {Path(_runbook(rule)).name for rule in alert_rules(document)}
    for runbook in sorted(runbooks - pointed - UNPOINTED):
        print(f"report: no alert points at {runbook}; a procedure may exist without an alert")
    return violations


def run(root: Path) -> list[Violation]:
    """Read the alerts, the runbook directory and the SLO ledger, and make them agree."""
    alerts = root / ALERTS
    slos = root / SLOS
    if not alerts.exists() or not slos.exists():
        return [Violation(ALERTS.as_posix(), 1, "the alerts or the SLO ledger is missing")]
    document = yaml.safe_load(alerts.read_text(encoding="utf-8"))
    runbooks = {
        path.name for path in (root / RUNBOOKS).glob("*.md") if path.name not in rules.SKIP_DIRS
    }
    text = slos.read_text(encoding="utf-8")
    headings = {
        name: headings_of((root / RUNBOOKS / name).read_text(encoding="utf-8")) for name in runbooks
    }
    return (
        alert_violations(document, runbooks, ALERTS.as_posix())
        + about_violations(document, headings)
        + coverage_violations(document, text, runbooks)
    )
