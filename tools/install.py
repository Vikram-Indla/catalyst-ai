"""`make tools`: the pinned binaries the gate needs, from archives whose SHA-256 is pinned.

A binary reaches .tools/bin/<os>-<arch> only by extraction from an archive whose digest matches
its line in tools/checksums.sha256 (the vendor's own checksum lines, copied when a version moves).
Nothing on PATH and nothing already in .tools/bin is trusted: the archive is verified and the
binary extracted again on every run; the verified archive is kept in .tools/archives.

Two groups: the gate's tools (`make tools`), and the scanner (`make scan-tools`, `--scan`), which
only the image scan needs. The gate never downloads the scanner, so the pipeline stays offline
after its first run.
"""

import hashlib
import io
import platform
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TOOL_VERSIONS = Path(".tool-versions")
TOOLS_DIR = Path(".tools") / "bin"
ARCHIVES = Path(".tools") / "archives"
CHECKSUMS = Path("tools") / "checksums.sha256"
GITHUB = "https://github.com"
RELEASES = {
    "gitleaks": "{g}/gitleaks/gitleaks/releases/download/v{v}/gitleaks_{v}_{os}_{arch}.{ext}",
    "oasdiff": "{g}/oasdiff/oasdiff/releases/download/v{v}/oasdiff_{v}_{os}_{arch}.{ext}",
    "trivy": "{g}/aquasecurity/trivy/releases/download/v{v}/trivy_{v}_{os}-{arch}.{ext}",
}
GATE_TOOLS = ("gitleaks", "oasdiff")
SCAN_TOOLS = ("trivy",)
ZIPPED_ON_WINDOWS = frozenset({"gitleaks", "trivy"})
ARCHES = {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}
OASDIFF_ARCHES = {"x64": "amd64", "arm64": "arm64"}
TRIVY_SYSTEMS = {"linux": "Linux", "darwin": "macOS", "windows": "windows"}
TRIVY_ARCHES = {"x64": "64bit", "arm64": "ARM64"}


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
    ext = "zip" if system == "windows" and tool in ZIPPED_ON_WINDOWS else "tar.gz"
    if tool == "oasdiff":
        arch = OASDIFF_ARCHES.get(arch, arch)
    if tool == "trivy":
        system, arch = TRIVY_SYSTEMS.get(system, system), TRIVY_ARCHES.get(arch, arch)
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


def pinned_digests() -> dict[str, str]:
    """Return archive name -> SHA-256 from the pin file."""
    pairs = (
        line.split() for line in CHECKSUMS.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    return {name: digest for digest, name in pairs}


def _verified_archive(tool: str, version: str) -> bytes:
    url = _url(tool, version)
    name = url.rsplit("/", 1)[1]
    expected = pinned_digests().get(name)
    if expected is None:
        message = f"{name} has no pinned checksum in {CHECKSUMS}; add the vendor's line first"
        raise RuntimeError(message)
    cached = ARCHIVES / name
    if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == expected:
        return cached.read_bytes()
    print(f"downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 — pinned GitHub release URL
        archive: bytes = response.read()
    actual = hashlib.sha256(archive).hexdigest()
    if actual != expected:
        message = f"{name}: sha256 {actual} does not match the pinned {expected}; refused"
        raise RuntimeError(message)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(archive)
    return archive


def install(tool: str, version: str) -> Path:
    """Extract one pinned binary from its verified archive, replacing whatever was there."""
    archive = _verified_archive(tool, version)
    destination = target_dir() / binary_name(tool)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _extract(archive, binary_name(tool), destination)
    return destination


def main(argv: list[str] | None = None) -> int:
    """Install the gate's pinned binaries (or, with `--scan`, the scanner) and print where."""
    pinned = versions()
    group = SCAN_TOOLS if "--scan" in (argv or []) else GATE_TOOLS
    for tool in group:
        print(f"{tool} {pinned[tool]} -> {install(tool, pinned[tool])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
