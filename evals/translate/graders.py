"""Deterministic graders for translate: script, structure, kept spans, names, length, safety."""

import re
from collections.abc import Callable

from catalyst_ai.capabilities.improve_story.quality import length_ratio
from catalyst_ai.capabilities.translate.quality import (
    in_target_script,
    kept_spans,
    structure_preserved,
)
from catalyst_ai.contract.translate import TranslateMode, TranslateRequest, TranslateResponse
from catalyst_ai.platform.safety import scan_output
from catalyst_ai.platform.safety.delimit import MARKER_PATTERN

Grader = Callable[[TranslateRequest, TranslateResponse, dict[str, object]], float]
MIN_RATIO = 0.3
MAX_RATIO = 3.0
TITLE_MAX_RATIO = 2.5
NAME_LIKE = re.compile(r"\b[A-Z][a-z]{2,}\b")
MID_SENTENCE_NAME = re.compile(r"(?<=[a-z,] )[A-Z][a-z]{2,}\b")


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def schema_valid(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """The translation is non-empty and names the target it was asked for."""
    del expected
    return _score(
        bool(response.translated_text.strip())
        and response.target_language == request.target_language
        and 0.0 <= response.confidence <= 1.0
    )


def target_script(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """The letters of the translation are in the target language's script."""
    del expected
    return _score(in_target_script(response.translated_text, request.target_language or "en"))


def detected_language_correct(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """The detected source language matches the case's."""
    del request
    return _score(response.detected_language.split("-")[0] == str(expected.get("source", "")))


def structure_kept(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """In field mode the Markdown skeleton survives; in title mode the result is one line."""
    del expected
    if request.mode is TranslateMode.TITLE:
        return _score("\n" not in response.translated_text.strip())
    return _score(structure_preserved(request.text, response.translated_text))


def spans_kept(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """Keys, links, code, placeholders survive exactly."""
    del expected
    return _score(set(kept_spans(request.text)) <= set(kept_spans(response.translated_text)))


def no_name_like_introduced(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """No mid-sentence capitalised word appears in a Latin-script output the source lacks."""
    del expected
    if (request.target_language or "").startswith("ar"):
        return 1.0
    source = request.text + "\n" + (request.context or "")
    source_words = {w.lower() for w in NAME_LIKE.findall(source)} | set(kept_spans(source))
    introduced = {
        w
        for w in MID_SENTENCE_NAME.findall(response.translated_text)
        if w.lower() not in source_words
    }
    return _score(not introduced)


def length_bounds(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """A translation is neither a stub nor a runaway."""
    del expected
    ratio = length_ratio(request.text, response.translated_text)
    ceiling = TITLE_MAX_RATIO if request.mode is TranslateMode.TITLE else MAX_RATIO
    return _score(MIN_RATIO <= ratio <= ceiling)


def no_forbidden_content(
    request: TranslateRequest, response: TranslateResponse, expected: dict[str, object]
) -> float:
    """The output scanner finds nothing; no fence marker echoed."""
    del expected
    texts = [request.text, request.context or ""]
    return _score(
        not scan_output(response.translated_text, texts)
        and not MARKER_PATTERN.search(response.translated_text)
    )


GRADERS: dict[str, Grader] = {
    "schema_valid": schema_valid,
    "target_script": target_script,
    "detected_language_correct": detected_language_correct,
    "structure_kept": structure_kept,
    "spans_kept": spans_kept,
    "no_name_like_introduced": no_name_like_introduced,
    "length_bounds": length_bounds,
    "no_forbidden_content": no_forbidden_content,
}
