"""Which sets a change can move: its capability's own, every set when the ground moved, none."""

from pathlib import Path

from tools.affected import affected_sets, package_of
from tools.evalkit import REGISTRY

SETS = sorted(REGISTRY)
ROOT = Path.cwd()


def test_every_registered_set_names_a_capability_package() -> None:
    for name in SETS:
        package = package_of(name, ROOT)
        assert (ROOT / "src" / "catalyst_ai" / "capabilities" / package).is_dir(), name
    assert package_of("documents-generate", ROOT) == "documents"
    assert package_of("propose-workflow", ROOT) == "propose_workflow"
    assert package_of("nothing-here", ROOT) == "nothing_here"


def test_a_capability_change_picks_its_sets_and_a_platform_change_picks_all() -> None:
    own = affected_sets(["src/catalyst_ai/capabilities/documents/ask.py"], SETS, ROOT)
    assert own == ["documents", "documents-generate", "documents-ingest"]
    fixture = affected_sets(["tests/fixtures/providers/gemini/summarize/x.json"], SETS, ROOT)
    assert fixture == ["summarize"]
    graders = affected_sets(["evals/translate/graders.py"], SETS, ROOT)
    assert graders == ["translate"]
    assert affected_sets(["src/catalyst_ai/platform/pipeline/stages.py"], SETS, ROOT) == SETS
    assert affected_sets(["tools/authored.py"], SETS, ROOT) == SETS
    assert affected_sets(["uv.lock"], SETS, ROOT) == SETS


def test_docs_tests_and_the_checks_move_no_set() -> None:
    quiet = ["docs/04-ledgers/config.md", "tests/unit/tools/test_affected.py", "tools/checks/ci.py"]
    assert affected_sets(quiet, SETS, ROOT) == []
    assert affected_sets([], SETS, ROOT) == []
