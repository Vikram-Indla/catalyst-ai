"""Parsing runs in a child process with a deadline and a memory ceiling; on budget it is killed."""

import asyncio
import base64
import importlib
import json
import subprocess
import sys
from dataclasses import asdict

from catalyst_ai.retrieval.parsers import Block, Parsed, ParserError, Reason, parse

WORKER = "from catalyst_ai.retrieval.runner import worker_main; worker_main()"
DEFAULT_TIMEOUT_S = 20.0
MEMORY_CEILING_BYTES = 1_024 * 1024 * 1024
RECURSION_LIMIT = 2_000
MAX_OUTPUT_BYTES = 64 * 1024 * 1024


def _limit_memory() -> None:
    try:
        resource = importlib.import_module("resource")
    except ImportError:
        return
    ceiling = (MEMORY_CEILING_BYTES, MEMORY_CEILING_BYTES)
    resource.setrlimit(resource.RLIMIT_AS, ceiling)


def worker_main() -> None:
    """Read `{format, payload_base64}` on stdin; write the blocks or the reason on stdout."""
    _limit_memory()
    sys.setrecursionlimit(RECURSION_LIMIT)
    request = json.loads(sys.stdin.read())
    try:
        parsed = parse(request["format"], base64.b64decode(request["payload_base64"]))
        answer = {"ok": True, "blocks": [asdict(block) for block in parsed.blocks]}
    except ParserError as error:
        answer = {"ok": False, "reason": error.reason.value, "message": error.message}
    sys.stdout.write(json.dumps(answer))


def _decode(raw: bytes) -> Parsed:
    try:
        answer = json.loads(raw)
    except ValueError as error:
        raise ParserError(Reason.MALFORMED, "the parser answered nothing readable") from error
    if not answer.get("ok"):
        reason = Reason(answer.get("reason", Reason.MALFORMED.value))
        raise ParserError(reason, str(answer.get("message", "the parser refused the document")))
    blocks = [Block(tuple(b["heading_path"]), b["text"]) for b in answer["blocks"]]
    return Parsed(blocks)


def parse_bounded(fmt: str, payload: bytes, timeout_s: float = DEFAULT_TIMEOUT_S) -> Parsed:
    """Parse in a child process: killed at the deadline, refused on a crash, bounded in memory."""
    request = json.dumps({"format": fmt, "payload_base64": base64.b64encode(payload).decode()})
    try:
        completed = subprocess.run(
            [sys.executable, "-c", WORKER],
            input=request.encode(),
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ParserError(
            Reason.TIMEOUT, "the parser ran past its deadline and was killed"
        ) from error
    if completed.returncode != 0 or len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise ParserError(Reason.MALFORMED, "the parser stopped before answering")
    return _decode(completed.stdout)


async def parse_document(fmt: str, payload: bytes, timeout_s: float = DEFAULT_TIMEOUT_S) -> Parsed:
    """Run the bounded parse off the event loop."""
    return await asyncio.to_thread(parse_bounded, fmt, payload, timeout_s)
