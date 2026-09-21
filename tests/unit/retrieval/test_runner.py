"""The bounded runner: a child parse round trip, the deadline, a crash, the hostile corpus."""

import importlib
import io
import json
import sys
import time
from pathlib import Path

import pytest

from catalyst_ai.retrieval import runner
from catalyst_ai.retrieval.parsers import Parsed, ParserError, Reason
from catalyst_ai.retrieval.runner import _decode, parse_bounded, parse_document, worker_main
from tests.conftest import REPO_ROOT

HOSTILE = REPO_ROOT / "tests" / "fixtures" / "documents" / "hostile"
FORMATS = {".docx": "docx", ".pptx": "pptx", ".pdf": "pdf", ".md": "markdown", ".txt": "text"}
LIMIT_S = 15.0
SAFE = {"injection.md", "restricted.md"}


def test_round_trip_through_the_child() -> None:
    parsed = parse_bounded("markdown", b"# T\n\nbody\n", timeout_s=LIMIT_S)
    assert [(b.heading_path, b.text) for b in parsed.blocks] == [(("T",), "body")]


async def test_async_wrapper_and_a_refusal_crosses_the_boundary() -> None:
    parsed = await parse_document("text", b"a\n\nb", timeout_s=LIMIT_S)
    assert [b.text for b in parsed.blocks] == ["a", "b"]
    with pytest.raises(ParserError) as caught:
        await parse_document("docx", b"nope", timeout_s=LIMIT_S)
    assert caught.value.reason is Reason.MALFORMED
    with pytest.raises(ParserError) as unsupported:
        parse_bounded("xlsx", b"x", timeout_s=LIMIT_S)
    assert unsupported.value.reason is Reason.UNSUPPORTED


def test_the_child_is_killed_on_the_deadline() -> None:
    started = time.perf_counter()
    with pytest.raises(ParserError) as caught:
        parse_bounded("text", b"slow", timeout_s=0.001)
    assert caught.value.reason is Reason.TIMEOUT
    assert time.perf_counter() - started < LIMIT_S


def test_an_unreadable_answer_is_a_malformed_document() -> None:
    with pytest.raises(ParserError) as unreadable:
        _decode(b"not json")
    assert unreadable.value.reason is Reason.MALFORMED
    with pytest.raises(ParserError) as refused:
        _decode(json.dumps({"ok": False, "reason": "document_timeout", "message": "m"}).encode())
    assert refused.value.reason is Reason.TIMEOUT
    assert _decode(json.dumps({"ok": True, "blocks": []}).encode()) == Parsed([])


def test_worker_answers_json_on_stdout(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    request = json.dumps({"format": "text", "payload_base64": "aGVsbG8="})
    monkeypatch.setattr(sys, "stdin", io.StringIO(request))
    worker_main()
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "blocks": [{"heading_path": [], "text": "hello"}],
    }
    monkeypatch.setattr(
        sys, "stdin", io.StringIO(json.dumps({"format": "docx", "payload_base64": "eA=="}))
    )
    worker_main()
    assert json.loads(capsys.readouterr().out)["reason"] == "document_malformed"


def test_a_crashed_child_is_a_malformed_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "WORKER", "import sys; sys.exit(3)")
    with pytest.raises(ParserError) as crashed:
        parse_bounded("text", b"x", timeout_s=LIMIT_S)
    assert crashed.value.reason is Reason.MALFORMED
    monkeypatch.setattr(runner, "MAX_OUTPUT_BYTES", 1)
    monkeypatch.setattr(runner, "WORKER", 'print(\'{"ok": true, "blocks": []}\')')
    with pytest.raises(ParserError) as flooded:
        parse_bounded("text", b"x", timeout_s=LIMIT_S)
    assert flooded.value.reason is Reason.MALFORMED


def test_the_memory_ceiling_is_set_where_the_platform_offers_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, tuple[int, int]]] = []

    class FakeResource:
        RLIMIT_AS = 9

        @staticmethod
        def setrlimit(which: int, limits: tuple[int, int]) -> None:
            calls.append((which, limits))

    monkeypatch.setattr(importlib, "import_module", lambda _name: FakeResource)
    runner._limit_memory()
    assert calls == [(9, (runner.MEMORY_CEILING_BYTES, runner.MEMORY_CEILING_BYTES))]

    def _missing(_name: str) -> object:
        raise ImportError

    monkeypatch.setattr(importlib, "import_module", _missing)
    runner._limit_memory()
    assert len(calls) == 1


def _outcome(path: Path) -> Parsed | ParserError:
    try:
        return parse_bounded(FORMATS[path.suffix], path.read_bytes(), timeout_s=LIMIT_S)
    except ParserError as error:
        return error


@pytest.mark.parametrize("path", sorted(HOSTILE.iterdir()), ids=lambda p: p.name)
def test_every_hostile_sample_ends_inside_the_limit_with_a_class(path: Path) -> None:
    started = time.perf_counter()
    outcome = _outcome(path)
    assert time.perf_counter() - started < LIMIT_S
    if isinstance(outcome, ParserError):
        assert path.name not in SAFE
        assert outcome.reason.value.startswith("document_")
        assert path.name not in outcome.message
    else:
        assert path.name in SAFE
        assert outcome.blocks
