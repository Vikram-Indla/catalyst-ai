"""`make tools`: a binary reaches .tools/bin only from an archive whose SHA-256 is pinned."""

import gzip
import hashlib
import io
import platform
import tarfile
import time
import urllib.request
from pathlib import Path

import pytest

from tools import install

TOOL = "gitleaks"
VERSION = "8.30.1"
GENUINE = b"genuine binary"


def _archive(payload: bytes) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as bundle:
        info = tarfile.TarInfo(install.binary_name(TOOL))
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))
    return gzip.compress(buffer.getvalue(), mtime=0)


def _archive_name() -> str:
    return install._url(TOOL, VERSION).rsplit("/", 1)[1]


class Release:
    """The release server: serves one archive and counts the downloads."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, served: bytes) -> None:
        self.served = served
        self.downloads = 0
        monkeypatch.setattr(urllib.request, "urlopen", self.urlopen)

    def urlopen(self, _url: str, timeout: int) -> io.BytesIO:
        """Answer one download the way `urllib.request.urlopen` does."""
        assert timeout > 0
        self.downloads += 1
        return io.BytesIO(self.served)


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A repository root whose pin file names the genuine archive and nothing else."""
    monkeypatch.chdir(tmp_path)
    pins = tmp_path / "tools" / "checksums.sha256"
    pins.parent.mkdir()
    digest = hashlib.sha256(_archive(GENUINE)).hexdigest()
    pins.write_text(f"{digest}  {_archive_name()}\n", encoding="utf-8")
    return tmp_path


def _plant_shim(directory: Path) -> Path:
    directory.mkdir()
    if platform.system() == "Windows":
        shim = directory / f"{TOOL}.bat"
        shim.write_text(f"@echo {TOOL} version {VERSION}\n", encoding="utf-8")
    else:
        shim = directory / TOOL
        shim.write_text(f"#!/bin/sh\necho {TOOL} version {VERSION}\n", encoding="utf-8")
        shim.chmod(0o755)
    return shim


def test_a_shim_on_the_path_that_prints_the_pinned_version_is_not_trusted(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim = _plant_shim(workdir / "shims")
    monkeypatch.setenv("PATH", str(shim.parent))
    release = Release(monkeypatch, _archive(GENUINE))
    installed = install.install(TOOL, VERSION)
    assert installed == install.target_dir() / install.binary_name(TOOL), f"accepted {installed}"
    assert installed.read_bytes() == GENUINE
    assert release.downloads == 1


def test_a_download_whose_digest_is_not_the_pinned_one_is_refused_and_lands_nowhere(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    Release(monkeypatch, _archive(b"tampered binary"))
    with pytest.raises(RuntimeError, match="does not match the pinned"):
        install.install(TOOL, VERSION)
    assert not (install.target_dir() / install.binary_name(TOOL)).exists()
    assert not list(workdir.glob(".tools/archives/*"))


def test_a_binary_already_in_the_tools_directory_is_replaced_from_the_verified_archive(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    planted = workdir / install.target_dir() / install.binary_name(TOOL)
    planted.parent.mkdir(parents=True)
    planted.write_bytes(b"planted binary")
    Release(monkeypatch, _archive(GENUINE))
    assert install.install(TOOL, VERSION).read_bytes() == GENUINE


def test_a_version_without_a_pinned_checksum_is_refused_before_any_download(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = Release(monkeypatch, _archive(GENUINE))
    with pytest.raises(RuntimeError, match="no pinned checksum"):
        install.install(TOOL, "8.30.2")
    assert release.downloads == 0


def test_a_verified_archive_is_downloaded_once_and_a_corrupted_cache_is_fetched_again(
    workdir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    release = Release(monkeypatch, _archive(GENUINE))
    install.install(TOOL, VERSION)
    install.install(TOOL, VERSION)
    assert release.downloads == 1
    (workdir / ".tools" / "archives" / _archive_name()).write_bytes(b"corrupted")
    assert install.install(TOOL, VERSION).read_bytes() == GENUINE
    assert release.downloads == 2


def test_the_served_archive_is_the_pinned_one_whichever_second_it_is_built_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pin is computed once and the archive built again; a clock tick must not tell them apart."""
    first = _archive(GENUINE)
    monkeypatch.setattr(time, "time", lambda: 4_102_444_800.0)
    assert _archive(GENUINE) == first
