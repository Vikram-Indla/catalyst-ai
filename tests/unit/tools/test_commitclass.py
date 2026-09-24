"""The commit's class check: each staged record is held to the files committed with it."""

from tools.checks import commitclass

RECORD_LOCAL = "```\nBlast radius:    LOCAL — one capability's grader\n```\n"


def test_a_local_record_committed_with_a_platform_file_is_red() -> None:
    staged = ["brain/sessions/2026-09/0-x.md", "src/catalyst_ai/config/settings.py"]
    found = commitclass.check(staged, {"brain/sessions/2026-09/0-x.md": RECORD_LOCAL})
    assert [v.message for v in found] == [
        "claims LOCAL but the files committed with it derive PLATFORM"
    ]


def test_the_same_record_with_only_its_own_files_is_green() -> None:
    staged = ["brain/sessions/2026-09/0-x.md", "tools/checks/prclass.py", "tests/unit/tools/t.py"]
    assert commitclass.check(staged, {"brain/sessions/2026-09/0-x.md": RECORD_LOCAL}) == []


def test_a_committed_record_without_a_claim_is_red() -> None:
    found = commitclass.check(
        ["brain/sessions/2026-09/0-x.md"], {"brain/sessions/2026-09/0-x.md": "x"}
    )
    assert [v.message for v in found] == [commitclass.NO_CLAIM]


def test_a_commit_without_a_record_is_not_judged() -> None:
    assert commitclass.check(["src/catalyst_ai/providers/port.py"], {}) == []
