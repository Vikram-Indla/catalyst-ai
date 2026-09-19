"""RULE-008: prompts are versioned files with a header; no prompt string in a pipeline."""

import ast
import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative, walk

CAPABILITIES = rules.SRC / "capabilities"
PROMPT_FILE = re.compile(r"^prompt_v(?P<version>\d+)\.md$")
HEADER = re.compile(r"^---\n(?P<body>.*?)\n---", re.S)
ASSEMBLE = "assemble"


def _looks_like_prompt(value: str) -> bool:
    return len(value) >= rules.PROMPT_MIN_LENGTH and any(
        marker in value for marker in rules.PROMPT_MARKERS
    )


def header_violations(text: str, where: str) -> list[Violation]:
    """Report a prompt file without the header or with a key missing."""
    match = HEADER.match(text)
    if match is None:
        return [Violation(where, 1, "prompt file lacks the header block")]
    keys = {line.split(":")[0].strip() for line in match.group("body").splitlines() if ":" in line}
    return [
        Violation(where, 1, f"prompt header lacks {key}")
        for key in rules.PROMPT_HEADER_KEYS
        if key not in keys
    ]


def _assemble_functions(module: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(module)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == ASSEMBLE
    ]


def _docstrings(module: ast.Module) -> set[int]:
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found: set[int] = set()
    for node in ast.walk(module):
        if isinstance(node, owners) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                found.add(id(first.value))
    return found


def _code_violations(path: Path, root: Path) -> list[Violation]:
    violations = []
    where = relative(path, root)
    module = parse(path)
    docstrings = _docstrings(module)
    for node in ast.walk(module):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings
            and _looks_like_prompt(node.value)
        ):
            violations.append(
                Violation(where, node.lineno, "a prompt string in code; prompts are files")
            )
    for function in _assemble_functions(module):
        for node in ast.walk(function):
            if isinstance(node, ast.JoinedStr):
                violations.append(
                    Violation(
                        where, node.lineno, "an f-string in assemble; fill named placeholders"
                    )
                )
    return violations


def run(root: Path) -> list[Violation]:
    """Check every capability's code and prompt files."""
    violations = []
    for path in walk(root, CAPABILITIES):
        violations += _code_violations(path, root)
    for path in walk(root, CAPABILITIES, suffix=".md"):
        if PROMPT_FILE.match(path.name):
            violations += header_violations(path.read_text(encoding="utf-8"), relative(path, root))
    return violations
