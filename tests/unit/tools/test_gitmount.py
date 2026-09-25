"""The gate's image reads git and never writes it: read-only mounts, no optional locks."""

from pathlib import Path

from tools.checks import gitmount

ROOT = Path(__file__).resolve().parents[3]
READ_ONLY = 'docker run -v "$(G)":/gitcommon:ro -e GIT_OPTIONAL_LOCKS=0 -e GIT_DIR=/gitcommon/x img'


def test_a_read_only_mount_without_optional_locks_passes() -> None:
    assert gitmount.check(READ_ONLY, "w") == []


def test_a_writable_mount_is_refused_on_its_line() -> None:
    text = READ_ONLY + '\ndocker run -v "$(G)":/gitcommon -e GIT_DIR=/gitcommon/x img\n'
    found = gitmount.check(text, "w")
    assert [(v.line, v.message) for v in found] == [
        (2, "the git common directory is mounted writable")
    ]


def test_git_in_the_image_without_the_lock_switch_is_refused() -> None:
    text = 'docker run -v "$(G)":/gitcommon:ro img\n'
    assert [v.message for v in gitmount.check(text, "w")] == [
        "git runs in the image without GIT_OPTIONAL_LOCKS=0"
    ]


def test_a_makefile_that_mounts_no_git_owes_nothing() -> None:
    assert gitmount.check("test:\n\tpytest\n", "w") == []


def test_the_repository_makefile_passes() -> None:
    assert gitmount.run(ROOT) == []
