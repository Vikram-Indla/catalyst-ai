"""The change-aware plan: the full pipeline unless the last green tree is a usable base."""

from tools import change_gate

NOW = 1_000_000.0
DIGEST = "sha256:abc"
BASE_FILES = {"src/a.py": "1", "docs/02-rules/r.md": "2", "tools/checks/c.py": "3"}


def _base(**overrides: object) -> dict[str, object]:
    stamp: dict[str, object] = {
        "digest": DIGEST,
        "at": NOW - 60,
        "manifest": BASE_FILES,
        "scope": "full",
    }
    stamp.update(overrides)
    return stamp


def test_no_base_another_image_or_an_old_base_is_the_full_pipeline() -> None:
    assert change_gate.plan(None, BASE_FILES, DIGEST, NOW).targets == ["ci"]
    assert change_gate.plan(_base(manifest=None), BASE_FILES, DIGEST, NOW).targets == ["ci"]
    assert change_gate.plan(_base(digest="other"), BASE_FILES, DIGEST, NOW).targets == ["ci"]
    stale = change_gate.plan(_base(at=NOW - 2 * change_gate.MAX_AGE_S), BASE_FILES, DIGEST, NOW)
    assert stale.targets == ["ci"]
    assert stale.reason == "the last green run is older than a day"


def test_a_docs_only_change_runs_only_the_docs_steps() -> None:
    current = {**BASE_FILES, "docs/02-rules/r.md": "changed"}
    decided = change_gate.plan(_base(), current, DIGEST, NOW)
    assert decided.targets == ["verify-docs"]
    assert decided.changed == ["docs/02-rules/r.md"]


def test_a_source_change_runs_everything_and_a_mixed_one_the_union() -> None:
    source = change_gate.plan(_base(), {**BASE_FILES, "src/a.py": "x"}, DIGEST, NOW)
    assert source.targets == ["ci"]
    mixed = {**BASE_FILES, "docs/02-rules/r.md": "x", "tools/checks/c.py": "y"}
    assert change_gate.plan(_base(), mixed, DIGEST, NOW).targets == ["verify-checks"]


def test_an_added_or_removed_file_is_a_change() -> None:
    added = change_gate.changed_paths(BASE_FILES, {**BASE_FILES, "brain/new.md": "n"})
    assert added == ["brain/new.md"]
    removed = {k: v for k, v in BASE_FILES.items() if k != "src/a.py"}
    assert change_gate.plan(_base(), removed, DIGEST, NOW).targets == ["ci"]


def test_the_same_tree_runs_nothing() -> None:
    decided = change_gate.plan(_base(), dict(BASE_FILES), DIGEST, NOW)
    assert decided.targets == []
    assert decided.reason == "the tree is the last green tree"


def test_a_scoped_run_is_never_a_base_so_a_chain_cannot_outlive_its_full_run() -> None:
    scoped = _base(scope="docs")
    assert change_gate.plan(scoped, BASE_FILES, DIGEST, NOW).reason == (
        "the base is a scoped run; only a full run is a base"
    )
    full_a = _base(at=NOW - 25 * 3600)
    docs_c = {**BASE_FILES, "docs/02-rules/r.md": "c"}
    decided = change_gate.plan(full_a, docs_c, DIGEST, NOW)
    assert decided.targets == ["ci"]
    assert decided.reason == "the last green run is older than a day"
