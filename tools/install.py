"""`make tools`: the pinned binaries the gate needs, downloaded once into .tools/bin/<os>-<arch>."""

import io
import platform
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TOOL_VERSIONS = Path(".tool-versions")
TOOLS_DIR = Path(".tools") / "bin"
GITHUB = "https://github.com"
RELEASES = {
    "gitleaks": "{g}/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_{os}_{arch}.{ext}",
    "oasdiff": "{g}/oasdiff/oasdiff/releases/download/v{v}/oasdiff_{v}_{os}_{arch}.{ext}",
}
ARCHES = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}
OASDIFF_ARCHES = {"x64": "amd64", "arm64": "arm64"}


def versions() -> dict[str, str]:
    """Return the pinned versions from .tool-versions."""
    pairs = (
        line.split()
        for line in TOOL_VERSIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    return dict(pairs)


def target_dir() -> Path:
    """Return the per-platform directory the binaries land in."""
    system = platform.system().lower()
    arch = ARCHES.get(platform.machine().lower(), platform.machine().lower())
    return TOOLS_DIR / f"{system}-{arch}"


def binary_name(tool: str) -> str:
    """Return the executable name on this platform."""
    return f"{tool}.exe" if platform.system() == "Windows" else tool


def _url(tool: str, version: str) -> str:
    system = platform.system().lower()
    arch = ARCHES.get(platform.machine().lower(), platform.machine().lower())
    ext = "zip" if system == "windows" and tool == "gitleaks" else "tar.gz"
    if tool == "oasdiff":
        arch = OASDIFF_ARCHES.get(arch, arch)
    return RELEASES[tool].format(g=GITHUB, v=version, os=system, arch=arch, ext=ext)


def _extract(archive: bytes, name: str, destination: Path) -> None:
    if archive[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            member = next(m for m in bundle.namelist() if m.endswith(name))
            destination.write_bytes(bundle.read(member))
    else:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            info = next(m for m in bundle.getmembers() if m.name.endswith(name))
            extracted = bundle.extractfile(info)
            if extracted is None:
                message = f"{name} is not a file in the archive"
                raise RuntimeError(message)
            destination.write_bytes(extracted.read())
    destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def install(tool: str, version: str) -> Path:
    """Download one pinned release unless the binary already exists."""
    destination = target_dir() / binary_name(tool)
    if destination.exists():
        return destination
    existing = shutil.which(tool)
    if existing and version in _version_of(existing):
        return Path(existing)
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = _url(tool, version)
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 — pinned GitHub release URL
        _extract(response.read(), binary_name(tool), destination)
    return destination


def _version_of(executable: str) -> str:
    completed = subprocess.run([executable, "version"], capture_output=True, text=True, check=False)
    return completed.stdout + completed.stderr


def main() -> int:
    """Install every pinned binary and print where it is."""
    pinned = versions()
    for tool in RELEASES:
        print(f"{tool} {pinned[tool]} -> {install(tool, pinned[tool])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
