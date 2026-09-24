"""`make ci-aware`: run what the changed files oblige, against the last green tree, or all of it.

The base is the last **full** green run (`stamp.read_base`): its manifest names every file of the
tree it proved, by blob. A scoped run is never a base, so a chain of scoped runs cannot outlive
the full run under it. The files whose blob differs from the base are the change, their classes
(`tools/change_map`) are the steps. No base, no manifest, a scoped stamp, another image, or a base
older than a day: the full pipeline. Any SOURCE or CONFIG file: the full pipeline. The hosted
workflow on `main` never reads this; it always runs everything.
"""

import subprocess
import sys
import time
from dataclasses import dataclass

from tools import change_map, ci_image, stamp

MAX_AGE_S = stamp.MAX_AGE_S


@dataclass(frozen=True)
class Plan:
    """What a change-aware run will do, and why."""

    targets: list[str]
    reason: str
    changed: list[str]


def changed_paths(base: dict[str, str], current: dict[str, str]) -> list[str]:
    """Return every path added, removed or changed between two manifests."""
    return sorted(p for p in base.keys() | current.keys() if base.get(p) != current.get(p))


def why_no_base(base: dict[str, object] | None, digest: str | None, now: float) -> str | None:
    """Return why the last green stamp cannot be the base of a change-aware run, or None."""
    if base is None:
        return "no full green run on record"
    checks = (
        (base.get("scope") != stamp.FULL, "the base is a scoped run; only a full run is a base"),
        (base.get("digest") != digest, "the last green run used another image"),
        (now - float(str(base.get("at", 0))) > MAX_AGE_S, "the last green run is older than a day"),
    )
    return next((reason for failed, reason in checks if failed), None)


def plan(
    base: dict[str, object] | None,
    current: dict[str, str],
    digest: str | None,
    now: float,
) -> Plan:
    """Decide the targets from the last green stamp and the tree as it is."""
    manifest = base.get("manifest") if base else None
    unusable = why_no_base(base, digest, now)
    if unusable is not None or not isinstance(manifest, dict):
        return Plan(["ci"], unusable or "no green run with a manifest to compare against", [])
    changed = changed_paths({str(k): str(v) for k, v in manifest.items()}, current)
    classes = change_map.classes_of(changed)
    targets = change_map.targets_for(classes)
    reason = f"{len(changed)} file(s) differ from the last green tree: {', '.join(sorted(classes))}"
    return Plan(targets, reason if changed else "the tree is the last green tree", changed)


def main(argv: list[str]) -> int:
    """Print the plan; with `--run`, run it (the full pipeline, a scoped one, or nothing)."""
    image = ci_image.tag()
    decided = plan(stamp.read_base(), stamp.tree_manifest(), stamp.image_digest(image), time.time())
    print(f"ci-aware: {decided.reason} -> {' '.join(decided.targets) or 'nothing to run'}")
    for path in decided.changed[:20]:
        print(f"  {change_map.class_of(path) or change_map.CONFIG:7} {path}")
    if "--run" not in argv or not decided.targets:
        return 0
    if decided.targets == ["ci"]:
        return subprocess.run(["make", "--no-print-directory", "ci"], check=False).returncode
    scope = ",".join(sorted(change_map.classes_of(decided.changed)))
    command = ["make", "--no-print-directory", "ci-scoped", f"TARGETS={' '.join(decided.targets)}"]
    return subprocess.run([*command, f"SCOPE={scope}"], check=False).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
