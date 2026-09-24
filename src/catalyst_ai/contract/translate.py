"""The translate operation: one field or title into a named target language, structure kept.

A caller may send a glossary for the language pair, as data: governed terms, each with the one
target it must be rendered as. A term of the glossary found in the text is rendered with its exact
target, and the response names every term it enforced (`glossary_applied`). A term it could not
enforce is reported (`glossary_conflict`), never guessed: a source the glossary gives two targets,
or a term whose target the translation does not carry.
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TEXT = 20_000
MAX_TITLE_TEXT = 500
MAX_CONTEXT = 800
MAX_LANGUAGE = 16
MAX_OUTPUT_CHARS = 40_000
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"
MAX_GLOSSARY = 100
MAX_TERM = 120
MAX_NOTE = 300

ConflictReason = Literal["ambiguous_glossary", "term_not_rendered"]


class GlossaryEntry(BaseModel):
    """One governed term: the source, the one target it must become, a reviewer's note."""

    model_config = ConfigDict(extra="forbid")

    source: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TERM,
            json_schema_extra=classified(
                "INTERNAL", "The term as it appears in the source language"
            ),
        ),
    ]
    target: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TERM,
            json_schema_extra=classified("INTERNAL", "The exact rendering in the target language"),
        ),
    ]
    note: Annotated[
        str | None,
        Field(
            max_length=MAX_NOTE,
            json_schema_extra=classified(
                "CONFIDENTIAL", "A reviewer's note; data, never an instruction"
            ),
        ),
    ] = None


class GlossaryConflict(BaseModel):
    """A glossary term that was not enforced, and why; the reviewer decides, not the model."""

    model_config = ConfigDict(extra="forbid")

    source: str
    reason: ConflictReason


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
    glossary: Annotated[
        list[GlossaryEntry],
        Field(
            default_factory=list,
            max_length=MAX_GLOSSARY,
            json_schema_extra=classified("INTERNAL", "Governed terms for this language pair"),
        ),
    ]


class TranslateResponse(ResponseEnvelope):
    """The translation, the languages, whether the structure survived, the confidence."""

    model_config = ConfigDict(extra="forbid")

    translated_text: str = Field(max_length=MAX_OUTPUT_CHARS)
    detected_language: str
    target_language: str
    structure_preserved: bool
    confidence: float = Field(ge=0.0, le=1.0)
    glossary_applied: list[str] = Field(default_factory=list)
    glossary_conflict: list[GlossaryConflict] = Field(default_factory=list)
