"""Which eval sets a change can move: the capability's own, or every set when the ground moved.

Used by `make verify-fast` only — iteration, never evidence. `make verify` and `make ci` run
every set regardless.
"""

from pathlib import Path

from tools import rules

CAPABILITIES = Path("src/catalyst_ai/capabilities")
SHARED = (
    "src/catalyst_ai/platform/",
    "src/catalyst_ai/providers/",
    "src/catalyst_ai/retrieval/",
    "src/catalyst_ai/contract/",
    "src/catalyst_ai/config/",
    "src/catalyst_ai/app.py",
    "pyproject.toml",
    "uv.lock",
)
TOOLING_EXEMPT = "tools/checks/"


def package_of(set_name: str, root: Path) -> str:
    """Return the capability package a set belongs to: its name, or its name minus a mode suffix."""
    parts = set_name.split("-")
    while parts:
        candidate = "_".join(parts)
        if (root / CAPABILITIES / candidate).is_dir():
            return candidate
        parts.pop()
    return set_name.replace("-", "_")


def _moves_everything(path: str) -> bool:
    if path.startswith(SHARED):
        return True
    return path.startswith("tools/") and not path.startswith(TOOLING_EXEMPT)


def affected_sets(changed: list[str], sets: list[str], root: Path) -> list[str]:
    """Return the sets a change touches, in the order given."""
    if any(_moves_everything(path) for path in changed):
        return list(sets)
    picked = []
    for name in sets:
        own = (
            f"{CAPABILITIES.as_posix()}/{package_of(name, root)}/",
            f"{rules.EVALS.as_posix()}/{name}/",
            f"{rules.FIXTURES.as_posix()}/providers/gemini/{name}/",
        )
        if any(path.startswith(own) for path in changed):
            picked.append(name)
    return picked
