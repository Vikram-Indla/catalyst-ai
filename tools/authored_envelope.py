"""The provider-shaped envelope every authored answer is wrapped in."""

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
