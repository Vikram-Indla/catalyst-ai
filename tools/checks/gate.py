"""The gate kernel: violations, file walking, the runner every check module plugs into."""

from __future__ import annotations

import ast
import importlib
import io
import os
import sys
import tokenize
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from tools import rules
from tools.scope import scope_of, staged

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
PER_FILE = frozenset(
    {
        "filebudget",
        "funcbudget",
        "comments",
        "naming",
        "globals",
        "vocabulary",
        "network",
        "logs",
        "inline",
        "mypy_overrides",
    }
)
CODE_PREFIXES = tuple(f"{code_root.as_posix()}/" for code_root in rules.CODE_ROOTS)
CROSS_FILE_READS = {
    "deployment": ("deploy/", "src/catalyst_ai/config/"),
    "dupl": CODE_PREFIXES,
    "structure": CODE_PREFIXES,
}
SCOPE: ContextVar[frozenset[Path] | None] = ContextVar("scope", default=None)


@dataclass(frozen=True)
class Violation:
    """One finding: where, and what rule it breaks."""

    path: str
    line: int
    message: str

    def render(self) -> str:
        """Return the one-line form the gate prints."""
        return f"{self.path}:{self.line}: {self.message}"


def in_scope(path: Path) -> bool:
    """Whether a per-file check may read the file: always, unless a commit's scope is set."""
    scope = SCOPE.get()
    return scope is None or path.resolve() in scope


def scoped(root: Path, sub: Path, suffix: str) -> list[Path] | None:
    """Return the scope's files under `sub` with the suffix, or None when no scope is set."""
    scope = SCOPE.get()
    if scope is None:
        return None
    base = (root / sub).resolve()
    return [p for p in scope if p.suffix == suffix and p.is_relative_to(base) and p.is_file()]


def reads_staged(name: str, paths: list[str] | None) -> bool:
    """Whether a cross-file check reads anything the commit stages; always, with no staged list."""
    prefixes = CROSS_FILE_READS.get(name)
    return paths is None or prefixes is None or any(p.startswith(prefixes) for p in paths)


def relative(path: Path, root: Path) -> str:
    """Return a forward-slash path relative to the root, for messages and matching."""
    return path.relative_to(root).as_posix()


def walk(root: Path, *subdirs: Path, suffix: str = ".py") -> list[Path]:
    """Every file with the suffix under the subdirs, sorted; skip directories are never entered."""
    found: list[Path] = []
    for sub in subdirs:
        base = root / sub
        narrowed = scoped(root, sub, suffix)
        if narrowed is not None or not base.exists():
            found.extend(narrowed or [])
            continue
        for directory, names, files in os.walk(base):
            names[:] = sorted(n for n in names if n not in rules.SKIP_DIRS)
            found.extend(
                Path(directory) / f
                for f in sorted(files)
                if f.endswith(suffix) and in_scope(Path(directory) / f)
            )
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


def run_check(name: str, root: Path, scope: frozenset[Path] | None = None) -> list[Violation]:
    """Import the check module by name and run it; a per-file check reads only the scope."""
    module = importlib.import_module(f"tools.checks.{name}")
    token = SCOPE.set(scope if name in PER_FILE else None)
    try:
        result: list[Violation] = module.run(root)
    finally:
        SCOPE.reset(token)
    return result


def main(argv: list[str]) -> int:
    """Run every check (or the fast subset) in order; stop at the first red one.

    `--staged` gives the per-file checks only the commit's staged files. A cross-file check runs,
    on the whole repository, when a staged file is one it reads (`CROSS_FILE_READS`) or the change
    moves the ground (`tools/scope.py`). The hosted run reads everything.
    """
    root = Path.cwd().resolve()
    paths = staged(root) if "--staged" in argv else None
    scope = None if paths is None else frozenset((root / path).resolve() for path in paths)
    paths = None if paths is None or scope_of(root, paths) is None else paths
    fast = "--fast" in argv
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    skip = argv[argv.index("--skip") + 1].split(",") if "--skip" in argv else []
    names = [
        name
        for name in CHECKS
        if (not fast or name in FAST) and (only is None or name == only) and name not in skip
        if reads_staged(name, paths)
    ]
    for name in names:
        violations = run_check(name, root, scope)
        if violations:
            for violation in violations:
                print(violation.render())
            print(f"GATE RED at: {name} ({len(violations)} violations)")
            return 1
        print(f"ok   {name}")
    where = "" if scope is None else f", per-file checks on {len(scope)} staged files"
    print(f"GATE GREEN ({len(names)} checks{where})")
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
