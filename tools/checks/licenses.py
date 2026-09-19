"""ADR-003: every installed distribution carries a licence from the allowlist."""

from importlib import metadata
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation

CLASSIFIER_PREFIX = "License :: "
UNKNOWN = "unknown"
OWN_PACKAGE = "catalyst-ai"


def licence_of(distribution: metadata.Distribution) -> str:
    """Return the licence text of a distribution from its metadata or classifiers."""
    meta = distribution.metadata
    expression = meta.get("License-Expression") or ""
    if expression:
        return str(expression)
    classifiers = [c for c in meta.get_all("Classifier", []) if c.startswith(CLASSIFIER_PREFIX)]
    if classifiers:
        return "; ".join(classifiers)
    return str(meta.get("License") or UNKNOWN)


def check(distributions: list[tuple[str, str]]) -> list[Violation]:
    """Report every (name, licence) pair outside the allowlist."""
    violations = []
    for name, licence in distributions:
        if not any(allowed.lower() in licence.lower() for allowed in rules.LICENSE_ALLOWLIST):
            violations.append(
                Violation("uv.lock", 1, f"{name} has licence {licence!r}, outside the allowlist")
            )
    return violations


def run(root: Path) -> list[Violation]:
    """Inspect every distribution installed in the environment."""
    del root
    pairs = [
        (d.metadata["Name"] or UNKNOWN, licence_of(d))
        for d in metadata.distributions()
        if d.metadata["Name"] != OWN_PACKAGE
    ]
    return check(sorted(set(pairs)))
