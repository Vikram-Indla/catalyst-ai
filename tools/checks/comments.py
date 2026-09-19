"""RULE-001 §3: no comment but a directive with an allowlisted reason; directives never grow."""

import io
import re
import tokenize
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, python_files, relative

DIRECTIVE = re.compile(
    r"^#\s*(noqa:\s*[A-Z0-9, ]+|type:\s*ignore\[[a-z-]+\]|pragma:\s*no cover)"
    r"\s*[—#-]+\s*(?P<reason>.+)$"
)
FILE_DIRECTIVES = ("#!", "# ruff:", "# mypy:", "# fmt:", "# pyright:")


def _classify(comment: str) -> str | None:
    problem = None
    match = DIRECTIVE.match(comment)
    if comment.startswith(FILE_DIRECTIVES):
        problem = None
    elif match is None:
        problem = "a comment that is not a directive with a reason"
    elif match.group("reason").strip() not in rules.DIRECTIVE_REASONS:
        problem = f"directive reason {match.group('reason').strip()!r} is not in the allowlist"
    return problem


def run(root: Path) -> list[Violation]:
    """Report non-directive comments, unknown reasons, and a directive count over the baseline."""
    violations = []
    directives = 0
    for path in python_files(root):
        text = path.read_text(encoding="utf-8")
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type != tokenize.COMMENT:
                continue
            problem = _classify(token.string)
            if problem is not None:
                violations.append(Violation(relative(path, root), token.start[0], problem))
            elif not token.string.startswith(FILE_DIRECTIVES):
                directives += 1
    if directives > rules.DIRECTIVE_BASELINE:
        message = (
            f"{directives} directives; the baseline is {rules.DIRECTIVE_BASELINE} and may only fall"
        )
        violations.append(Violation("tools/rules.py", 1, message))
    return violations
