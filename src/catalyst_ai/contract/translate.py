"""The translate operation: one field or title into a named target language, structure kept."""

from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TEXT = 20_000
MAX_TITLE_TEXT = 500
MAX_CONTEXT = 800
MAX_LANGUAGE = 16
MAX_OUTPUT_CHARS = 40_000
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"


class TranslateMode(StrEnum):
    """`field` keeps paragraphs and Markdown; `title` returns one line."""

    FIELD = "field"
    TITLE = "title"


class TranslateRequest(RequestEnvelope):
    """The text, its optional context, the target — required, refused at the door when absent."""

    model_config = ConfigDict(extra="forbid")

    mode: Annotated[
        TranslateMode,
        Field(json_schema_extra=classified("PUBLIC", "field (paragraphs, Markdown) or title")),
    ]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The text to translate"),
        ),
    ]
    context: Annotated[
        str | None,
        Field(
            max_length=MAX_CONTEXT,
            json_schema_extra=classified(
                "CONFIDENTIAL", "Surrounding text that resolves pronouns and tone; not translated"
            ),
        ),
    ] = None
    source_language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent means detect"),
        ),
    ] = None
    target_language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified(
                "PUBLIC", "BCP 47 tag; absent is refused (translation always has a target)"
            ),
        ),
    ] = None


class TranslateResponse(ResponseEnvelope):
    """The translation, the languages, whether the structure survived, the confidence."""

    model_config = ConfigDict(extra="forbid")

    translated_text: str = Field(max_length=MAX_OUTPUT_CHARS)
    detected_language: str
    target_language: str
    structure_preserved: bool
    confidence: float = Field(ge=0.0, le=1.0)
