"""The release workflow's row: one job, id-token alone, the settings from variables, print-only."""

from pathlib import Path

import yaml

from tools import rules
from tools.checks import release_job

COMMITTED = rules.RELEASE_WORKFLOW.read_text(encoding="utf-8")
WHERE = rules.RELEASE_WORKFLOW.as_posix()


def violations(text: str) -> list[str]:
    loaded = yaml.safe_load(text)
    document = {"on" if key is True else key: value for key, value in loaded.items()}
    return [v.message for v in release_job.check(document, text, WHERE)]


def test_the_committed_workflow_passes() -> None:
    assert violations(COMMITTED) == []


def test_an_action_or_a_release_that_is_not_print_only_is_refused() -> None:
    action = COMMITTED.replace(
        "      - run: make release RELEASE_FLAGS=--print",
        "      - uses: google-github-actions/auth@v2\n      - run: make release",
    )
    found = violations(action)
    assert any("uses google-github-actions/auth@v2" in m for m in found)
    assert any("runs 'make release'" in m for m in found)


def test_a_setting_written_in_the_file_or_a_wider_permission_is_refused() -> None:
    written = COMMITTED.replace("${{ vars.RELEASE_LOCATION }}", "somewhere-1")
    assert any("job key 'env'" in m for m in violations(written))
    wider = COMMITTED.replace("contents: read", "contents: write")
    assert any("job key 'permissions'" in m for m in violations(wider))


def test_the_file_exists_where_the_gate_reads_it() -> None:
    assert Path(WHERE).is_file()
