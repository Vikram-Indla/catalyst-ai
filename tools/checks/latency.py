"""Every latency alert judges an operation by the budget its capability declares (`ARCH-008 §1`).

One threshold for every operation is an alert that is silent for most of them: `improve-story`
declares 4 s, so an 8 s rule lets it run at twice its budget without a word. The descriptor is
where the budget is declared and the eval gate holds it; this check holds the alerts to it.
Every served operation is selected by exactly one request latency rule whose threshold is its
capability's `p95_latency_ms`, every capability by exactly one provider latency rule, and every
threshold is a bucket edge, because a quantile interpolated across its threshold measures nothing.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from tools import rules
from tools.checks.alerts import ALERTS, alert_rules
from tools.checks.capabilities import read_descriptor
from tools.checks.gate import Violation

OPENAPI = Path("api") / "openapi.yaml"
METRICS = Path("platform") / "observability" / "metrics.py"
REQUEST_SERIES = "catalyst_ai_http_request_duration_seconds_bucket"
PROVIDER_SERIES = "catalyst_ai_provider_call_duration_seconds_bucket"
LATENCY_FIELD = "p95_latency_ms"
MS_PER_SECOND = 1000
UNJUDGED = {
    "health.live": "a probe; no capability runs behind it",
    "health.ready": "a probe; no capability runs behind it",
    "jobs.get": "a poll of a stored row; no capability runs behind it",
    "documents.ingest_job": "answers 202 once the row is stored; the work is the job's",
}
MATCHER = re.compile(r'(\w+)\s*(=~|!~|!=|=)\s*"([^"]*)"')
THRESHOLD = re.compile(r">\s*([0-9]+(?:\.[0-9]+)?)\s*$")


@dataclass(frozen=True)
class LatencyRule:
    """One latency alert: which label values it selects and the p95 it fires above, in seconds."""

    alert: str
    op: str
    pattern: str
    threshold: float

    def selects(self, value: str) -> bool:
        """Apply the rule's label matcher as the rule engine would (anchored)."""
        if self.op == "=":
            return value == self.pattern
        if self.op == "!=":
            return value != self.pattern
        matched = re.fullmatch(self.pattern, value) is not None
        return matched if self.op == "=~" else not matched


def latency_rules(document: object, series: str, label: str) -> list[LatencyRule]:
    """Read the rules over one duration histogram, with their matcher on `label`."""
    found = []
    for rule in alert_rules(document):
        expr = str(rule.get("expr", ""))
        if series not in expr:
            continue
        matchers = [m for m in MATCHER.findall(expr) if m[0] == label]
        threshold = THRESHOLD.search(expr.strip())
        op, pattern = (matchers[0][1], matchers[0][2]) if matchers else ("=~", ".*")
        value = float(threshold.group(1)) if threshold else -1.0
        found.append(LatencyRule(str(rule.get("alert", "")), op, pattern, value))
    return found


def thresholds_for(value: str, judged_by: list[LatencyRule]) -> list[float]:
    """Return the thresholds, in seconds, of the rules that select `value`."""
    return [rule.threshold for rule in judged_by if rule.selects(value)]


def check(
    budgets: dict[str, int], judged_by: list[LatencyRule], edges: set[float], what: str
) -> list[Violation]:
    """Report a value judged by no rule, by two, or by a threshold that is not its budget."""
    violations = []
    where = ALERTS.as_posix()
    for value, budget_ms in sorted(budgets.items()):
        found = thresholds_for(value, judged_by)
        if len(found) != 1:
            violations.append(
                Violation(where, 1, f"{what} {value} is judged by {len(found)} rules")
            )
        elif round(found[0] * MS_PER_SECOND) != budget_ms:
            violations.append(
                Violation(
                    where, 1, f"{what} {value} fires above {found[0]} s; budget {budget_ms} ms"
                )
            )
    for rule in judged_by:
        if rule.threshold not in edges:
            violations.append(
                Violation(
                    where, 1, f"{rule.alert} fires above {rule.threshold} s, not a bucket edge"
                )
            )
    return violations


def _budgets(root: Path) -> dict[str, int]:
    budgets = {}
    for path in sorted((root / rules.SRC / "capabilities").glob("*/descriptor.py")):
        values = read_descriptor(path, root).values
        latency = values.get(LATENCY_FIELD)
        if isinstance(latency, int):
            budgets[str(values.get("name", ""))] = latency
    return budgets


def _operations(root: Path) -> dict[str, str]:
    document = yaml.safe_load((root / OPENAPI).read_text(encoding="utf-8"))
    return {
        str(operation["operationId"]): str(operation.get("x-capability", ""))
        for methods in document.get("paths", {}).values()
        for operation in methods.values()
        if isinstance(operation, dict) and "operationId" in operation
    }


def _edges(root: Path) -> set[float]:
    tree = ast.parse((root / rules.SRC / METRICS).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "BUCKETS_S" for t in node.targets
        ):
            return {float(v) for v in ast.literal_eval(node.value)}
    return set()


def run(root: Path) -> list[Violation]:
    """Hold the request and provider latency rules to the descriptors' budgets."""
    document = yaml.safe_load((root / ALERTS).read_text(encoding="utf-8"))
    budgets = _budgets(root)
    edges = _edges(root)
    violations = []
    served: dict[str, int] = {}
    for operation, capability in _operations(root).items():
        if operation in UNJUDGED:
            continue
        if capability not in budgets:
            violations.append(Violation(OPENAPI.as_posix(), 1, f"{operation} has no budget"))
            continue
        served[operation] = budgets[capability]
    requests = latency_rules(document, REQUEST_SERIES, "operation")
    providers = latency_rules(document, PROVIDER_SERIES, "capability")
    return (
        violations
        + check(served, requests, edges, "operation")
        + check(budgets, providers, edges, "capability")
    )
