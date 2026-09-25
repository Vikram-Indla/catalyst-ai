"""ARCH-003, RULE-009: every capability has its descriptor, eval set, budget, settings, switch."""

import ast
from dataclasses import dataclass
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, parse, relative

REQUIRED_KEYS = (
    "name",
    "version",
    "prompt_version",
    "eval_set_version",
    "kind",
    "p95_latency_ms",
    "p95_cost_micros",
    "timeout_ms",
    "kill_switch",
)
EVAL_FILES = ("set.jsonl", "thresholds.yaml", "README.md")
SYNC_KINDS = frozenset({"sync", "stream"})
SETTINGS_FILE = rules.SRC / "config" / "settings.py"


@dataclass(frozen=True)
class Descriptor:
    """Return the parsed constants of one descriptor module."""

    path: str
    values: dict[str, object]


def read_descriptor(path: Path, root: Path) -> Descriptor:
    """Collect the module-level constant assignments of a descriptor."""
    values: dict[str, object] = {}
    for node in parse(path).body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Constant)
        ):
            values[node.targets[0].id] = node.value.value
    return Descriptor(relative(path, root), values)


def settings_fields(root: Path) -> set[str]:
    """Return the field names of the Settings class."""
    path = root / SETTINGS_FILE
    if not path.exists():
        return set()
    return {
        statement.target.id
        for node in ast.walk(parse(path))
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
        for statement in node.body
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
    }


def check(descriptor: Descriptor, eval_files: set[str], settings: set[str]) -> list[Violation]:
    """Report what one capability lacks."""
    violations = []
    values = descriptor.values
    for key in REQUIRED_KEYS:
        if key not in values:
            violations.append(Violation(descriptor.path, 1, f"descriptor lacks {key}"))
    name = str(values.get("name", ""))
    snake = name.replace("-", "_")
    for file in EVAL_FILES:
        if file not in eval_files:
            violations.append(Violation(descriptor.path, 1, f"no evals/{name}/{file}"))
    if f"capability_{snake}" not in settings:
        violations.append(Violation(descriptor.path, 1, f"no settings row capability_{snake}"))
    expected_switch = f"CATALYST_AI_CAPABILITY_{snake.upper()}__ENABLED"
    if values.get("kill_switch") != expected_switch:
        violations.append(Violation(descriptor.path, 1, f"kill_switch must be {expected_switch}"))
    timeout = values.get("timeout_ms")
    if (
        values.get("kind") in SYNC_KINDS
        and isinstance(timeout, int)
        and timeout > rules.JOB_LINE_MS
    ):
        violations.append(
            Violation(
                descriptor.path,
                1,
                f"synchronous timeout {timeout} ms exceeds the job line {rules.JOB_LINE_MS}",
            )
        )
    return violations


def run(root: Path) -> list[Violation]:
    """Check every capability package in the tree."""
    violations = []
    settings = settings_fields(root)
    for path in sorted((root / rules.SRC / "capabilities").glob("*/descriptor.py")):
        descriptor = read_descriptor(path, root)
        evals = root / rules.EVALS / str(descriptor.values.get("name", ""))
        files = {p.name for p in evals.iterdir()} if evals.is_dir() else set()
        violations += check(descriptor, files, settings)
    return violations
