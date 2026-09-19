"""RULE-003 §1: the committed document equals the app's; every operation is complete."""

from pathlib import Path
from typing import Any

from tools import api, rules
from tools.checks.gate import Violation

REQUIRED_EXTENSIONS = ("x-capability", "x-capability-version", "x-error-codes")
REQUEST_SUFFIX = "Request"


def operation_violations(document: dict[str, Any], where: str) -> list[Violation]:
    """Report operations missing the extensions or an example, and unclassified request fields."""
    violations = []
    for path, item in document.get("paths", {}).items():
        for method, operation in item.items():
            label = f"{method.upper()} {path}"
            for key in REQUIRED_EXTENSIONS:
                if key not in operation:
                    violations.append(Violation(where, 1, f"{label} lacks {key}"))
            ok_response = operation.get("responses", {}).get("200", {})
            if "x-example" not in ok_response and "example" not in str(ok_response):
                violations.append(Violation(where, 1, f"{label} lacks an example"))
    for name, schema in document.get("components", {}).get("schemas", {}).items():
        if name.endswith(REQUEST_SUFFIX):
            for field, spec in schema.get("properties", {}).items():
                if "data_class" not in spec:
                    violations.append(Violation(where, 1, f"{name}.{field} lacks data_class"))
    return violations


def drift_violations(
    committed: dict[str, Any] | None, rendered: dict[str, Any], where: str
) -> list[Violation]:
    """Report a committed document that differs from the rendered one."""
    if committed is None:
        return [Violation(where, 1, "the document is not committed; run `make api`")]
    if committed != rendered:
        return [Violation(where, 1, "the document drifts from the app; run `make api`")]
    return []


def run(root: Path) -> list[Violation]:
    """Render the app's document and compare it with the committed file."""
    target = root / rules.API_DOCUMENT
    rendered = api.render()
    committed = api.load(target) if target.exists() else None
    where = rules.API_DOCUMENT.as_posix()
    return drift_violations(committed, rendered, where) + operation_violations(rendered, where)
