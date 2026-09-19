"""The replay transport: adapters in tests talk to fixtures, never to a provider."""

import hashlib
import json
from pathlib import Path

import httpx

FIXTURE_SUFFIX = ".json"
HASH_LENGTH = 16


class MissingFixtureError(Exception):
    """A request has no recorded fixture; the message carries the hash a recording needs."""

    def __init__(self, fixture_hash: str, method: str, url: str) -> None:
        """Name the missing fixture."""
        super().__init__(f"no fixture {fixture_hash} for {method} {url}")
        self.fixture_hash = fixture_hash


def fixture_hash(method: str, url: str, body: bytes) -> str:
    """Hash the parts of a request that decide its fixture; headers never take part."""
    digest = hashlib.sha256()
    digest.update(method.upper().encode())
    digest.update(b"\n")
    digest.update(url.encode())
    digest.update(b"\n")
    digest.update(body)
    return digest.hexdigest()[:HASH_LENGTH]


class RecordedTransport(httpx.AsyncBaseTransport):
    """Serve responses from `<directory>/<hash>.json`; refuse a request without one."""

    def __init__(self, directory: Path) -> None:
        """Bind the transport to a fixture directory."""
        self._directory = directory

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Look the request up by hash and replay the recorded status and body."""
        body = request.read()
        key = fixture_hash(request.method, str(request.url), body)
        path = self._directory / f"{key}{FIXTURE_SUFFIX}"
        if not path.is_file():
            raise MissingFixtureError(key, request.method, str(request.url))
        recorded = json.loads(path.read_text(encoding="utf-8"))
        return httpx.Response(
            status_code=int(recorded["status"]),
            headers=dict(recorded.get("headers", {})),
            content=json.dumps(recorded["body"]).encode(),
            request=request,
        )


def write_fixture(directory: Path, key: str, status: int, body: object) -> Path:
    """Persist a recorded response under its hash; used by the recording command."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{key}{FIXTURE_SUFFIX}"
    path.write_text(json.dumps({"status": status, "body": body}, indent=2), encoding="utf-8")
    return path
