"""RULE-000 §3: no id of the lead's private planning, no name of its files, no name of its people.

The check names shapes, never what they mean, and assembles them at run time so the shapes
never sit in the tree; it reads every text file of the repository and skips only its own
source. Its plant is a value the self-test builds in memory, for the same reason.
"""

import re
from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, relative

OWN_SOURCE = Path("tools") / "checks" / "vocabulary.py"
TEXT_SUFFIXES = (
    ".py",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".sql",
    ".txt",
    ".jsonl",
    ".json",
    ".example",
    ".cfg",
    ".ini",
    ".sh",
)
MAX_BYTES = 4 << 20
MESSAGE = "a word of the shape this repository never carries"


def _shapes() -> list[re.Pattern[str]]:
    prefixes = ["CA" + "T", "D" + "D", "D" + "Q", "D" + "F"]
    file_mark = "OUT" + "BOX-"
    slugs = [
        "no" + "or-po",
        "il" + "ya-go",
        "pri" + "ya-web",
        "raf" + "ael-ai",
        "han" + "na-infra",
        "ken" + "ji-devops",
    ]
    return [
        re.compile(r"\b(" + "|".join(prefixes) + r")-\d{3}\b"),
        re.compile(re.escape(file_mark)),
        re.compile(r"(?i)\b(" + "|".join(re.escape(slug) for slug in slugs) + r")\b"),
    ]


def check_lines(
    lines: list[str], where: str, shapes: list[re.Pattern[str]] | None = None
) -> list[Violation]:
    """Report every line of a file that carries one of the shapes."""
    patterns = shapes or _shapes()
    return [
        Violation(where, number, MESSAGE)
        for number, line in enumerate(lines, start=1)
        if any(pattern.search(line) for pattern in patterns)
    ]


def _text_files(root: Path) -> list[Path]:
    found = []
    for path in sorted(root.rglob("*")):
        if any(part in rules.SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix in TEXT_SUFFIXES and path.stat().st_size <= MAX_BYTES:
            found.append(path)
    return found


def run(root: Path) -> list[Violation]:
    """Report every text file of the repository carrying a shape, except this check's own source."""
    shapes = _shapes()
    violations: list[Violation] = []
    for path in _text_files(root):
        where = relative(path, root)
        if Path(where) == OWN_SOURCE:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        violations += check_lines(lines, where, shapes)
    return violations
