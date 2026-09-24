"""The change map is trusted only while every file has a class and no page a test reads is DOCS.

A change-aware run skips steps by the class of what changed, so a wrong class is a skipped test.
Three things are red: a tracked file no row matches; a row that puts source, tests, eval sets, the
contract or the migrations anywhere but SOURCE; and a page under `docs/` or `brain/` that a test,
an eval grader or the service itself names, while the map calls it DOCS. The map's own test
names pages to assert their class, not to read them, and is not scanned.
"""

import re
import subprocess
from pathlib import Path

from tools import change_map
from tools.checks.gate import Violation

MAP = "tools/change_map.py"
PAGE = re.compile(r"[\"'](?P<page>(?:docs|brain)/[^\"'\s]+\.md)[\"']")
READERS = ("src/", "tests/", "evals/")
CLASSIFIERS = frozenset({"tests/unit/tools/test_change_map.py"})
PROBE = "probe.py"


def check(
    tracked: list[str], rows: tuple[tuple[str, str], ...], reads: dict[str, set[str]]
) -> list[Violation]:
    """Report a file without a class, a misfiled source prefix, and a read page filed as DOCS."""
    violations = [
        Violation(path, 1, "no row of the change map matches this file")
        for path in tracked
        if change_map.class_of(path, rows) is None
    ]
    violations += [
        Violation(MAP, 1, f"{prefix} must be SOURCE; the map files it as {cls}")
        for prefix in change_map.MUST_BE_SOURCE
        if (cls := change_map.class_of(prefix + PROBE, rows)) != change_map.SOURCE
    ]
    for reader, pages in sorted(reads.items()):
        violations += [
            Violation(reader, 1, f"reads {page}, which the change map files as DOCS")
            for page in sorted(pages)
            if change_map.class_of(page, rows) == change_map.DOCS
        ]
    return violations


def pages_read(root: Path, tracked: list[str]) -> dict[str, set[str]]:
    """Return, per test, grader or source file, the existing pages under docs/ or brain/ it names.

    A name that is no file of the tree is test data, not a read.
    """
    present = set(tracked)
    reads: dict[str, set[str]] = {}
    for path in tracked:
        if path.startswith(READERS) and path.endswith(".py") and path not in CLASSIFIERS:
            text = (root / path).read_text(encoding="utf-8", errors="replace")
            found = {m.group("page") for m in PAGE.finditer(text)} & present
            if found:
                reads[path] = found
    return reads


def run(root: Path) -> list[Violation]:
    """Classify every tracked file and every page the code names."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout
    tracked = sorted(p for p in listed.split("\0") if p and (root / p).is_file())
    return check(tracked, change_map.ROWS, pages_read(root, tracked))
