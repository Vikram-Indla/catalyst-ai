"""The gate kernel: violations, file walking, the runner every check module plugs into."""

from __future__ import annotations

import ast
import importlib
import io
import os
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

from tools import rules

CHECKS = (
    "filebudget",
    "funcbudget",
    "structure",
    "comments",
    "naming",
    "dupl",
    "globals",
    "boundary",
    "readonly",
    "origin",
    "residency",
    "vocabulary",
    "alerts",
    "latency",
    "change_map",
    "classification",
    "routes",
    "contract",
    "ports",
    "openapi",
    "changelog",
    "errors",
    "config",
    "network",
    "logs",
    "tenancy",
    "sql",
    "migrations",
    "deadlines",
    "tasks",
    "inline",
    "interfaces",
    "tests",
    "fuzz",
    "deps",
    "licenses",
    "ci",
    "images",
    "commits",
    "sessions",
    "prclass",
    "commitclass",
    "commitsize",
    "localrun",
    "gitmount",
    "deployment",
    "invariants",
    "mypy_overrides",
    "capabilities",
    "prompts",
    "pipeline",
    "models",
    "evals",
    "budgets",
    "deprecations",
    "flags",
    "journeys",
    "coverage",
)
FAST = frozenset(
    {
        "filebudget",
        "funcbudget",
        "structure",
        "comments",
        "naming",
        "dupl",
        "globals",
        "inline",
        "logs",
        "network",
        "mypy_overrides",
        "vocabulary",
        "commitclass",
        "commitsize",
        "localrun",
        "gitmount",
        "deployment",
    }
)


@dataclass(frozen=True)
class Violation:
    """One finding: where, and what rule it breaks."""

    path: str
    line: int
    message: str

    def render(self) -> str:
        """Return the one-line form the gate prints."""
        return f"{self.path}:{self.line}: {self.message}"


def relative(path: Path, root: Path) -> str:
    """Return a forward-slash path relative to the root, for messages and matching."""
    return path.relative_to(root).as_posix()


def walk(root: Path, *subdirs: Path, suffix: str = ".py") -> list[Path]:
    """Every file with the suffix under the subdirs, sorted; skip directories are never entered."""
    found: list[Path] = []
    for sub in subdirs:
        base = root / sub
        if not base.exists():
            continue
        for directory, names, files in os.walk(base):
            names[:] = sorted(n for n in names if n not in rules.SKIP_DIRS)
            found.extend(Path(directory) / f for f in sorted(files) if f.endswith(suffix))
    return sorted(found)


def python_files(root: Path) -> list[Path]:
    """Every Python file of the code roots."""
    return walk(root, *rules.CODE_ROOTS)


def parse(path: Path) -> ast.Module:
    """Parse a file; a syntax error is a violation the caller reports."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def logical_lines(text: str) -> int:
    """Count lines that are not blank, not a comment and not inside a docstring."""
    count = 0
    docstring_rows: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.STRING and token.start[1] == 0:
                docstring_rows.update(range(token.start[0], token.end[0] + 1))
    except tokenize.TokenError:
        return len(text.splitlines())
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and number not in docstring_rows:
            count += 1
    return count


def run_check(name: str, root: Path) -> list[Violation]:
    """Import the check module by name and run it against the root."""
    module = importlib.import_module(f"tools.checks.{name}")
    result: list[Violation] = module.run(root)
    return result


def main(argv: list[str]) -> int:
    """Run every check (or the fast subset) in order; stop at the first red one."""
    root = Path.cwd()
    fast = "--fast" in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    skip = argv[argv.index("--skip") + 1].split(",") if "--skip" in argv else []
    names = [
        name
        for name in CHECKS
        if (not fast or name in FAST) and (only is None or name == only) and name not in skip
    ]
    for name in names:
        violations = run_check(name, root)
        if violations:
            for violation in violations:
                print(violation.render())
            print(f"GATE RED at: {name} ({len(violations)} violations)")
            return 1
        print(f"ok   {name}")
    print(f"GATE GREEN ({len(names)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


def imported_names(tree: ast.AST) -> list[tuple[int, str]]:
    """Every dotted module name a tree imports, with the line it is imported on."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append((node.lineno, node.module))
    return found
