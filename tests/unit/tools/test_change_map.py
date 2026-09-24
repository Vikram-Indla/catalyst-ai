"""The change map: every file has a class, source is never DOCS, a page a test reads is not DOCS."""

from pathlib import Path

from tools import change_map
from tools.checks import change_map as check

DOCS_EVERYWHERE = (("*", change_map.DOCS),)


def test_the_committed_tree_is_fully_classed() -> None:
    assert check.run(Path()) == []


def test_classes_follow_the_rows_in_order() -> None:
    assert change_map.class_of("src/catalyst_ai/app.py") == change_map.SOURCE
    assert change_map.class_of("docs/04-ledgers/slos.md") == change_map.SOURCE
    assert change_map.class_of("docs/02-rules/RULE-005-git-and-sessions.md") == change_map.DOCS
    assert change_map.class_of("brain/01-STATUS.md") == change_map.DOCS
    assert change_map.class_of("tools/checks/ci.py") == change_map.CHECKS
    assert change_map.class_of("tools/change_map.py") == change_map.CONFIG
    assert change_map.class_of("evals/search/README.md") == change_map.SOURCE


def test_mixed_classes_run_the_union_and_source_runs_everything() -> None:
    assert change_map.targets_for({change_map.DOCS}) == ["verify-docs"]
    assert change_map.targets_for({change_map.DOCS, change_map.CHECKS}) == ["verify-checks"]
    assert change_map.targets_for({change_map.DOCS, change_map.SOURCE}) == ["ci"]
    assert change_map.targets_for(set()) == []
    assert change_map.classes_of(["somewhere/new.bin"]) == {change_map.CONFIG}


def test_an_unmatched_file_is_refused() -> None:
    found = check.check(["notes.txt"], change_map.ROWS, {})
    assert [v.message for v in found] == ["no row of the change map matches this file"]


def test_a_page_a_test_reads_filed_as_docs_is_refused() -> None:
    reads = {"tests/unit/x_test.py": {"docs/01-architecture/ARCH-001-overview.md"}}
    found = check.check([], change_map.ROWS, reads)
    assert [v.message for v in found] == [
        "reads docs/01-architecture/ARCH-001-overview.md, which the change map files as DOCS"
    ]


def test_an_eval_file_filed_as_docs_is_refused() -> None:
    found = [v.message for v in check.check([], DOCS_EVERYWHERE, {})]
    assert "evals/ must be SOURCE; the map files it as docs" in found
    assert "src/ must be SOURCE; the map files it as docs" in found


def test_the_pages_code_names_are_found(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "t.py").write_text(
        'PAGE = "docs/06-runbooks/x.md"\nDATA = "docs/nowhere.md"\n', encoding="utf-8"
    )
    tracked = ["tests/t.py", "docs/06-runbooks/x.md"]
    assert check.pages_read(tmp_path, tracked) == {"tests/t.py": {"docs/06-runbooks/x.md"}}
