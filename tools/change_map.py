"""The path → class map a change-aware run reads: what a changed file obliges the pipeline to run.

Rows are matched in order and the first one wins; a tracked file no row matches is red
(`tools/checks/change_map`). DOCS runs every check, the selftest and the secret scan, because the
checks are what read the pages; CHECKS adds lint, types and the tools' tests; SOURCE and CONFIG run
the full pipeline. A page a test or the service itself reads is SOURCE, not DOCS, because a
docs-only run does not run the tests: the ledgers and runbooks the tests assert on, the eval sets'
own pages, and the prompts. The map itself is CONFIG, so a change to it runs everything.
"""

from fnmatch import fnmatchcase

DOCS = "docs"
CHECKS = "checks"
SOURCE = "source"
CONFIG = "config"
FULL = frozenset({SOURCE, CONFIG})

ROWS: tuple[tuple[str, str], ...] = (
    ("src/*", SOURCE),
    ("tests/*", SOURCE),
    ("evals/*", SOURCE),
    ("api/*", SOURCE),
    ("db/*", SOURCE),
    ("ops/*", SOURCE),
    ("docs/04-ledgers/*", SOURCE),
    ("docs/06-runbooks/*", SOURCE),
    ("tools/checks/*", CHECKS),
    ("tools/*", CONFIG),
    (".github/*", CONFIG),
    (".githooks/*", CONFIG),
    ("Makefile", CONFIG),
    ("Dockerfile", CONFIG),
    ("Dockerfile.ci", CONFIG),
    ("docker-compose.yml", CONFIG),
    ("pyproject.toml", CONFIG),
    ("uv.lock", CONFIG),
    (".tool-versions", CONFIG),
    ("*.ini", CONFIG),
    ("*.toml", CONFIG),
    (".importlinter", CONFIG),
    (".coveragerc", CONFIG),
    (".gitignore", CONFIG),
    (".gitattributes", CONFIG),
    (".dockerignore", CONFIG),
    (".env.example", CONFIG),
    ("docs/*", DOCS),
    ("brain/*", DOCS),
    ("*.md", DOCS),
)
MUST_BE_SOURCE = ("src/", "tests/", "evals/", "api/", "db/")


def class_of(path: str, rows: tuple[tuple[str, str], ...] = ROWS) -> str | None:
    """Return the class of the first row the path matches, or None when no row does."""
    return next((cls for pattern, cls in rows if fnmatchcase(path, pattern)), None)


def classes_of(paths: list[str], rows: tuple[tuple[str, str], ...] = ROWS) -> set[str]:
    """Return the classes a set of changed paths falls into; an unmatched path counts as CONFIG."""
    return {class_of(path, rows) or CONFIG for path in paths}


def targets_for(classes: set[str]) -> list[str]:
    """Return the make targets a change of these classes runs; the full pipeline wins any tie."""
    if classes & FULL:
        return ["ci"]
    if CHECKS in classes:
        return ["verify-checks"]
    return ["verify-docs"] if DOCS in classes else []
