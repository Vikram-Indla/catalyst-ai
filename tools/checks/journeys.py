"""RULE-004 §3: every operation has a contract test; every listed error code is asserted."""

import re
from pathlib import Path
from typing import Any

from tools import api, rules
from tools.checks.gate import Violation, walk

TEST_DEF = re.compile(r"^(?:async )?def (?P<name>test_[a-z0-9_]+)\(", re.M)


def operations(document: dict[str, Any]) -> dict[str, list[str]]:
    """Map each operationId to the error codes the operation lists."""
    found = {}
    for item in document.get("paths", {}).values():
        for operation in item.values():
            found[str(operation.get("operationId", ""))] = list(operation.get("x-error-codes", []))
    return found


def check(ops: dict[str, list[str]], test_names: set[str], test_text: str) -> list[Violation]:
    """Report operations without a test and listed codes never asserted."""
    violations = []
    where = rules.CONTRACT_TESTS.as_posix()
    for operation_id, codes in ops.items():
        prefix = "test_" + operation_id.replace(".", "_") + "_"
        if not any(name.startswith(prefix) for name in test_names):
            violations.append(
                Violation(where, 1, f"no contract test named {prefix}* for {operation_id}")
            )
        for code in codes:
            if code not in test_text:
                violations.append(
                    Violation(
                        where, 1, f"{operation_id} lists {code} but no contract test asserts it"
                    )
                )
    return violations


def run(root: Path) -> list[Violation]:
    """Render the document and read the contract tests."""
    names: set[str] = set()
    text = ""
    for path in walk(root, rules.CONTRACT_TESTS):
        content = path.read_text(encoding="utf-8")
        text += content
        names |= {m.group("name") for m in TEST_DEF.finditer(content)}
    return check(operations(api.render()), names, text)
