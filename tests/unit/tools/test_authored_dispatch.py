"""The authored stand-in answers each capability's request with that capability's shape."""

import json

from tools import authored


def _body(*segments: str) -> dict[str, object]:
    return {"contents": [{"parts": [{"text": "\n\n".join(segments)}]}]}


def _answer_keys(body: dict[str, object]) -> set[str]:

    answer = authored.answer(body)
    return set(json.loads(answer["candidates"][0]["content"]["parts"][0]["text"]))


def test_an_improve_story_request_gets_a_rewrite_not_an_unfurl_card_or_a_workflow() -> None:
    body = _body(
        "developer",
        "<<<title>>>\nLogin\n<<<end title>>>",
        "<<<description>>>\nuser should login\n<<<end description>>>",
        "<<<focus_hint>>>\n(none)\n<<<end focus_hint>>>",
    )
    assert {"description", "changed", "rationale"} <= _answer_keys(body)


def test_an_unfurl_request_still_gets_the_card() -> None:
    body = _body("developer", "<<<title>>>\nX\n<<<end title>>>", "<<<text>>>\nY\n<<<end text>>>")
    assert {"summary", "facts"} <= _answer_keys(body)
