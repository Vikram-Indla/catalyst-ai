"""Plant."""
import httpx


def test_net() -> None:
    httpx.get("http://example.invalid")
