"""ARCH-002: no product schema, no product database, no call to the backend, port only."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation, imported_names, parse, relative, walk

NETWORK_MODULES = frozenset({"httpx", "socket", "urllib", "aiohttp", "requests"})
ADAPTER_PREFIX = "catalyst_ai.providers."
PORT_MODULES = frozenset({"catalyst_ai.providers.port", "catalyst_ai.providers"})


def _product_markers(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.SRC) + walk(root, rules.SRC, suffix=".sql"):
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(marker in line for marker in rules.PRODUCT_DATABASE_MARKERS):
                violations.append(
                    Violation(relative(path, root), number, "names the product database")
                )
            if any(marker in line for marker in rules.BACKEND_CALL_MARKERS):
                violations.append(
                    Violation(relative(path, root), number, "holds a way to call the backend")
                )
            if any(
                f'"{prefix}' in lowered or f"'{prefix}" in lowered
                for prefix in rules.PRODUCT_TABLE_PREFIXES
            ):
                violations.append(Violation(relative(path, root), number, "names a product table"))
    return violations


def _capability_imports(root: Path) -> list[Violation]:
    violations = []
    for path in walk(root, rules.SRC / "capabilities"):
        for line, name in imported_names(parse(path)):
            top = name.split(".")[0]
            if top in NETWORK_MODULES or top == "os":
                violations.append(
                    Violation(relative(path, root), line, f"a capability imports {name}")
                )
            if name.startswith(ADAPTER_PREFIX) and name not in PORT_MODULES:
                violations.append(
                    Violation(relative(path, root), line, f"a capability imports an adapter {name}")
                )
    return violations


def run(root: Path) -> list[Violation]:
    """Report product markers anywhere in src and forbidden imports inside capabilities."""
    return _product_markers(root) + _capability_imports(root)
