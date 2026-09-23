"""The run-once evidence: a green `make ci` stamps the tree it ran on; a push of that tree skips.

The stamp lives in the common git directory (shared by every worktree of the repository) and is
keyed by the hash of every tracked and untracked-but-not-ignored file as it is on disk, plus the
digest of the image the pipeline ran in. Same tree, same image, younger than a day → the push
needs no second run. Anything else → the pipeline runs.

`begin` notes the tree a run is about to prove, in the worktree's own git directory; `write` stamps
only that tree, and only if the tree is still that one when the run ends. A tree edited while the
pipeline ran was not proved: the run stays green, and no stamp is written for it.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

STAMP_NAME = "ci-green"
BEGIN_NAME = "ci-begin"
MAX_AGE_S = 24 * 60 * 60


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], capture_output=True, check=True, encoding="utf-8", errors="replace"
    )
    return completed.stdout


def tree_hash() -> str:
    """Return a hash of the working tree: every tracked or unignored file's content, by path.

    Only the files that exist (a tracked file deleted but not yet committed counts as absent,
    exactly as it will after its commit, so committing never moves the hash), each as git would
    store it — line endings normalised — so a worktree and the main checkout of the same tree
    hash alike whatever their endings on disk.
    """
    listed = _git("ls-files", "-z", "--cached", "--others", "--exclude-standard")
    present = sorted({p for p in listed.split("\0") if p and Path(p).is_file()})
    hashed = subprocess.run(
        ["git", "hash-object", "--stdin-paths"],
        input="\n".join(present) + "\n",
        capture_output=True,
        check=True,
        encoding="utf-8",
    ).stdout.split()
    digest = hashlib.sha256()
    for path, blob in zip(present, hashed, strict=True):
        digest.update(f"{path}\0{blob}\n".encode())
    return digest.hexdigest()


def image_digest(image: str) -> str | None:
    """Return the local id of the image, or None when it is not present."""
    completed = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", image],
        capture_output=True,
        check=False,
        encoding="utf-8",
    )
    return completed.stdout.strip() or None if completed.returncode == 0 else None


def stamp_path() -> Path:
    """Return the stamp's location: the common git directory, shared by every worktree."""
    return Path(_git("rev-parse", "--git-common-dir").strip()) / STAMP_NAME


def begin_path() -> Path:
    """Return where a run notes its tree: this worktree's own git directory, never shared."""
    return Path(_git("rev-parse", "--git-dir").strip()) / BEGIN_NAME


def begin() -> str:
    """Note the tree the run is about to prove."""
    tree = tree_hash()
    begin_path().write_text(tree + "\n", encoding="utf-8")
    return tree


def write(image: str) -> dict[str, object] | None:
    """Record a green run in the given image, if the tree is still the one noted at `begin`."""
    noted = begin_path()
    started = noted.read_text(encoding="utf-8").strip() if noted.exists() else None
    noted.unlink(missing_ok=True)
    tree = tree_hash()
    if started != tree:
        return None
    stamp: dict[str, object] = {
        "tree": tree,
        "image": image,
        "digest": image_digest(image),
        "at": int(time.time()),
        "when": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    stamp_path().write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    return stamp


def _read_stamp() -> dict[str, object] | None:
    path = stamp_path()
    if not path.exists():
        return None
    try:
        loaded: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return loaded


def _staleness(stamp: dict[str, object], image: str, now: float) -> str | None:
    age = now - float(str(stamp.get("at", 0)))
    checks = (
        (stamp.get("tree") != tree_hash(), "the tree changed since its last green run"),
        (
            stamp.get("image") != image or stamp.get("digest") != image_digest(image),
            "the image is not the one the green run used",
        ),
        (age > MAX_AGE_S, f"the green run is {age / 3600:.0f} h old (a day is the limit)"),
    )
    return next((reason for stale, reason in checks if stale), None)


def reason_to_run(image: str, now: float | None = None) -> str | None:
    """Return why the pipeline must run again, or None when the stamp proves this tree."""
    stamp = _read_stamp()
    if stamp is None:
        return "no readable stamp: this tree has no green run on record"
    return _staleness(stamp, image, now if now is not None else time.time())


def _check(image: str) -> int:
    reason = reason_to_run(image)
    if reason is None:
        stamp = _read_stamp() or {}
        print(f"stamp: tree {str(stamp.get('tree'))[:12]} green in {image} at {stamp.get('when')}")
        return 0
    print(f"stamp: {reason}")
    return 1


def _write(image: str) -> int:
    stamp = write(image)
    if stamp is None:
        print(
            "stamp: the tree changed while the pipeline ran (or no start was noted); "
            "no stamp written — run make ci again on the tree you mean to push"
        )
        return 0
    print(f"stamp: tree {str(stamp['tree'])[:12]} in {image} at {stamp['when']} -- green")
    return 0


def main(argv: list[str] | None = None) -> int:
    """`begin` before a run, `write --image X` after a green one, `check --image X` at a push."""
    parser = argparse.ArgumentParser(prog="stamp")
    parser.add_argument("command", choices=("begin", "write", "check", "tree"))
    parser.add_argument("--image", default="")
    args = parser.parse_args(argv)
    if args.command in {"begin", "tree"}:
        print(begin() if args.command == "begin" else tree_hash())
        return 0
    return _write(args.image) if args.command == "write" else _check(args.image)


if __name__ == "__main__":
    sys.exit(main())
