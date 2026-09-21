"""`make record`: write provider fixtures for a set — authored (stand-in) or live (a real key)."""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import SecretStr

from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.recorded import (
    EVENT_STREAM,
    FIXTURE_SUFFIX,
    fixture_hash,
    write_fixture,
    write_raw_fixture,
)
from tools import authored, evalkit, rules
from tools.authored_envelope import sse_of

KEY_VARIABLE = "CATALYST_AI_RECORD_PROVIDER_KEY"
MANIFEST = "_manifest.json"
EMBED_SUFFIX = ":batchEmbedContents"
STREAM_MARKER = ":streamGenerateContent"


class RecordingTransport(httpx.AsyncBaseTransport):
    """Answer from the stand-in or the live API, and write every answer under its hash."""

    def __init__(self, directory: Path, *, live: bool) -> None:
        """Bind the fixture directory; live mode delegates to a real HTTP transport."""
        self._directory = directory
        self._live = httpx.AsyncHTTPTransport() if live else None
        self.written: list[str] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Produce the answer, persist it, return it."""
        body = request.read()
        key = fixture_hash(request.method, str(request.url), body)
        if STREAM_MARKER in str(request.url):
            return await self._stream(request, key, body)
        if self._live is not None:
            upstream = await self._live.handle_async_request(request)
            status, payload = upstream.status_code, json.loads(await upstream.aread())
        elif str(request.url).endswith(EMBED_SUFFIX):
            status, payload = 200, authored.answer_embed(json.loads(body))
        else:
            status, payload = 200, authored.answer(json.loads(body))
        write_fixture(self._directory, key, status, payload)
        self.written.append(key)
        return httpx.Response(
            status_code=status, content=json.dumps(payload).encode(), request=request
        )

    async def _stream(self, request: httpx.Request, key: str, body: bytes) -> httpx.Response:
        """Record a streamed call as the event-stream text, verbatim or authored."""
        if self._live is not None:
            upstream = await self._live.handle_async_request(request)
            status, raw = upstream.status_code, (await upstream.aread()).decode()
        else:
            status, raw = 200, sse_of(authored.answer(json.loads(body)))
        write_raw_fixture(self._directory, key, status, raw)
        self.written.append(key)
        return httpx.Response(
            status_code=status,
            headers={"content-type": EVENT_STREAM},
            content=raw.encode(),
            request=request,
        )


async def record(name: str, *, live: bool) -> int:
    """Run every case of the set through the pipeline over the recording transport."""
    directory = evalkit.FIXTURES_ROOT / name
    for stale in directory.glob(f"*{FIXTURE_SUFFIX}"):
        if stale.name != MANIFEST:
            stale.unlink()
    settings = evalkit.inert_settings()
    if live:
        settings = settings.model_copy(
            update={"provider_gemini_api_key": SecretStr(os.environ[KEY_VARIABLE])}
        )
    transport = RecordingTransport(directory, live=live)
    spec = evalkit.REGISTRY[name]
    raised: list[str] = []
    async with evalkit.database(spec) as storage:
        runtime = evalkit.runtime_over(transport, settings, storage)
        if spec.setup is not None:
            await spec.setup(runtime, Path(rules.EVALS) / name)
        for case in evalkit.load_cases(Path(rules.EVALS) / name / "set.jsonl"):
            try:
                await spec.pipeline(
                    spec.request.model_validate(case.input), runtime, f"record-{case.id}"
                )
            except Error as error:
                raised.append(f"{case.id}: {error.code.value} {[d.code for d in error.details]}")
    for line in raised:
        print(f"raised  {line}")
    manifest = {
        "source": "live" if live else "authored stand-in (tools/authored.py)",
        "recorded_at": datetime.now(tz=UTC).isoformat(),
        "fixtures": len(transport.written),
    }
    (directory / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"recorded {len(transport.written)} fixtures for {name} ({manifest['source']})")
    return 0


def main(argv: list[str]) -> int:
    """`--set <name>` and either `--authored` or `--live` (the key from the environment)."""
    name = argv[argv.index("--set") + 1] if "--set" in argv else "improve-story"
    live = "--live" in argv
    if live and KEY_VARIABLE not in os.environ:
        print(f"record: {KEY_VARIABLE} is not set; nothing recorded")
        return 1
    return asyncio.run(record(name, live=live))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
