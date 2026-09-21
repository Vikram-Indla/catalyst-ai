"""The provider-shaped envelope every authored answer is wrapped in."""

import json
from typing import Any

CHARS_PER_TOKEN = 4


def envelope(body: dict[str, Any], text: str) -> dict[str, Any]:
    prompt_chars = sum(len(p.get("text", "")) for c in body["contents"] for p in c["parts"])
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}],
        "usageMetadata": {
            "promptTokenCount": prompt_chars // CHARS_PER_TOKEN,
            "candidatesTokenCount": len(text) // CHARS_PER_TOKEN,
        },
        "modelVersion": "authored-stand-in",
    }


STREAM_PIECE = 48


def sse_of(payload: dict[str, Any]) -> str:
    """Render an envelope as the event-stream text the streaming endpoint would send.

    The text arrives in pieces; the last chunk carries the finish reason, the usage and the
    model, as the real stream does.
    """
    text = "".join(
        str(part.get("text", "")) for part in payload["candidates"][0]["content"]["parts"]
    )
    pieces = [text[i : i + STREAM_PIECE] for i in range(0, len(text), STREAM_PIECE)] or [""]
    chunks: list[dict[str, Any]] = [
        {"candidates": [{"content": {"parts": [{"text": piece}]}}]} for piece in pieces
    ]
    chunks[-1]["candidates"][0]["finishReason"] = payload["candidates"][0].get("finishReason")
    chunks[-1]["usageMetadata"] = payload.get("usageMetadata", {})
    chunks[-1]["modelVersion"] = payload.get("modelVersion")
    return "".join("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n" for chunk in chunks)
