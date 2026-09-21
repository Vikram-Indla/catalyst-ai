"""ARCH-002, the assistant's rule: a read-only capability touches no network and no writer.

The packages named in `rules.READ_ONLY_CAPABILITIES` may read the index through retrieval but
never import a client, a socket, the ingest path or a storage writer; a member's turn can
therefore never fetch, never write, never remember.
"""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative, walk

NETWORK_MODULES = frozenset({"httpx", "socket", "urllib", "aiohttp", "requests", "asyncpg"})
WRITER_MODULES = frozenset(
    {
        "catalyst_ai.retrieval.ingest",
        "catalyst_ai.platform.storage",
        "catalyst_ai.platform.storage.postgres",
        "catalyst_ai.platform.storage.memory",
        "catalyst_ai.capabilities.documents.ingest",
    }
)
WRITER_CALLS = ("replace_document", "delete_documents", "touch_document", "upsert", "run_ingest")


def _violations_in(path: Path, root: Path) -> list[Violation]:
    violations = []
    module = parse(path)
    for line, name in imported_names(module):
        top = name.split(".")[0]
        if top in NETWORK_MODULES or top == "os":
            violations.append(Violation(relative(path, root), line, f"imports {name}"))
        if name in WRITER_MODULES or name.startswith("catalyst_ai.retrieval.ingest"):
            violations.append(Violation(relative(path, root), line, f"imports a writer {name}"))
    text = path.read_text(encoding="utf-8")
    for number, source in enumerate(text.splitlines(), start=1):
        if any(f".{call}(" in source or f" {call}(" in source for call in WRITER_CALLS):
            violations.append(Violation(relative(path, root), number, "calls a writer"))
    return violations


def run(root: Path) -> list[Violation]:
    """Report any network, writer or ingest use inside a read-only capability package."""
    violations: list[Violation] = []
    for name in rules.READ_ONLY_CAPABILITIES:
        for path in walk(root, rules.SRC / "capabilities" / name):
            violations += _violations_in(path, root)
    return violations
