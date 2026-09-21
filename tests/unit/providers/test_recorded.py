"""The replay transport: hash stability, replay, refusal, fixture writing."""

from pathlib import Path

import httpx
import pytest

from catalyst_ai.providers.recorded import (
    MissingFixtureError,
    RecordedTransport,
    fixture_hash,
    write_fixture,
    write_raw_fixture,
)


def test_hash_ignores_headers_and_is_stable() -> None:
    assert fixture_hash("post", "http://p/x", b"{}") == fixture_hash("POST", "http://p/x", b"{}")
    assert fixture_hash("POST", "http://p/x", b"{}") != fixture_hash("POST", "http://p/y", b"{}")


async def test_replays_a_recorded_response(tmp_path: Path) -> None:
    key = fixture_hash("POST", "http://p/x", b'{"a": 1}')
    write_fixture(tmp_path, key, 200, {"text": "hi"})
    async with httpx.AsyncClient(transport=RecordedTransport(tmp_path), timeout=1.0) as client:
        response = await client.post("http://p/x", content=b'{"a": 1}')
    assert response.status_code == 200
    assert response.json() == {"text": "hi"}


async def test_refuses_without_a_fixture(tmp_path: Path) -> None:
    async with httpx.AsyncClient(transport=RecordedTransport(tmp_path), timeout=1.0) as client:
        with pytest.raises(MissingFixtureError) as caught:
            await client.get("http://p/none")
    assert caught.value.fixture_hash in str(caught.value)


async def test_replays_a_raw_stream_verbatim(tmp_path: Path) -> None:
    key = fixture_hash("POST", "https://x/stream", b"{}")
    raw = 'data: {"a": 1}' + chr(10) * 2 + 'data: {"a": 2}' + chr(10) * 2
    write_raw_fixture(tmp_path, key, 200, raw)
    async with (
        httpx.AsyncClient(transport=RecordedTransport(tmp_path), timeout=1.0) as client,
        client.stream("POST", "https://x/stream", json={}) as response,
    ):
        lines = [line async for line in response.aiter_lines()]
    assert response.headers["content-type"] == "text/event-stream"
    assert [line for line in lines if line] == ['data: {"a": 1}', 'data: {"a": 2}']
