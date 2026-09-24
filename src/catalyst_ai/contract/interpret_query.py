"""The interpret-query operation: a sentence becomes a query in the grammar the backend sends.

The grammar is data: the fields a list can filter on, their types, the operators each accepts,
the values a field allows when it has a closed set, and the functions the query language knows.
The service never holds a copy of it, so a field the backend adds tomorrow is filterable the
moment it is sent, and a field the backend does not send can never appear in a query.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TEXT = 500
MAX_FIELDS = 64
MAX_VALUES = 200
MAX_FUNCTIONS = 64
MAX_NAME = 64
MAX_VALUE = 120
MAX_QUERY = 2_000
MAX_EXPLANATION = 300
MAX_UNRESOLVED = 20
MAX_TIMEZONE = 64
FIELD_NAME = r"^[A-Za-z][A-Za-z0-9_]{0,63}$"
FUNCTION_NAME = r"^[A-Za-z][A-Za-z0-9]{0,63}\(\)$"
TIMEZONE_SHAPE = r"^[A-Za-z]+(/[A-Za-z0-9_+-]+)*$"

FieldType = Literal["string", "user", "date", "array", "number"]
Operator = Literal[
    "=", "!=", "<", ">", "<=", ">=", "in", "not in", "is", "is not", "was", "changed"
]
Locale = Literal["en", "ar"]


class GrammarField(BaseModel):
    """One filterable field: its name in the query, its type, its operators, its closed values."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=FIELD_NAME)
    type: FieldType
    operators: list[Operator] = Field(min_length=1)
    values: list[Annotated[str, Field(min_length=1, max_length=MAX_VALUE)]] | None = Field(
        default=None,
        max_length=MAX_VALUES,
        description="The closed set of values, when the field has one; else any value of its type",
    )
    label: str | None = Field(default=None, max_length=MAX_NAME)


class GrammarFunction(BaseModel):
    """One function the query language knows, and the field type it stands in for."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=FUNCTION_NAME)
    type: FieldType


class Grammar(BaseModel):
    """The filter grammar as the backend holds it; the only fields and values a query may name."""

    model_config = ConfigDict(extra="forbid")

    fields: list[GrammarField] = Field(min_length=1, max_length=MAX_FIELDS)
    functions: list[GrammarFunction] = Field(default_factory=list, max_length=MAX_FUNCTIONS)


class InterpretQueryRequest(RequestEnvelope):
    """A member's sentence, the grammar it must become a query in, and the moment it was asked."""

    model_config = ConfigDict(extra="forbid")

    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The sentence the member typed"),
        ),
    ]
    grammar: Annotated[
        Grammar,
        Field(json_schema_extra=classified("INTERNAL", "The fields, operators and values allowed")),
    ]
    now: Annotated[
        datetime,
        Field(
            json_schema_extra=classified(
                "PUBLIC", "When the member asked, in the organisation's zone with its offset"
            )
        ),
    ]
    timezone: Annotated[
        str,
        Field(
            max_length=MAX_TIMEZONE,
            pattern=TIMEZONE_SHAPE,
            json_schema_extra=classified("PUBLIC", "The organisation's IANA zone"),
        ),
    ] = "Asia/Riyadh"
    locale: Annotated[
        Locale,
        Field(json_schema_extra=classified("PUBLIC", "The language the sentence is written in")),
    ] = "en"


class InterpretQueryResponse(ResponseEnvelope):
    """A query that parses against the grammar, what it means in one line, and what it left out."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(max_length=MAX_QUERY)
    explanation: str = Field(max_length=MAX_EXPLANATION)
    unresolved: list[Annotated[str, Field(max_length=MAX_VALUE)]] = Field(max_length=MAX_UNRESOLVED)
    confidence: float = Field(ge=0.0, le=1.0)
