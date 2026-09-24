"""The interpret-query operation: a sentence becomes a query in the grammar the backend sends.

The grammar is data: the fields a list can filter on, their types, the operators each accepts,
the values a field allows when it has a closed set, and the functions the query language knows.
The service never holds a copy of it, so a field the backend adds tomorrow is filterable the
moment it is sent, and a field the backend does not send can never appear in a query.

A list that speaks the list contract sends its declaration instead: the query-string parameters it
reads (each one comparison: equality, or one end of a range named `<field>From` / `<field>To`),
their types and closed values, the sorts it accepts, and whether it has free-text search. The
answer is then those parameters, by those exact names, in those formats, with Latin digits
whatever the sentence's script; anything the declaration does not hold is reported, never guessed.
A request carries a grammar or a declaration, never both.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import SkipJsonSchema

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
PARAM_NAME = r"^[a-z][A-Za-z0-9]{0,63}$"
SORT_NAME = r"^-?[a-z][A-Za-z0-9]{0,63}$"
MAX_SORTS = 32
ONE_SHAPE = "send a grammar or a list declaration, exactly one"

ListingType = Literal["enum", "date", "datetime", "text", "number"]

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


class ListingFilter(BaseModel):
    """One parameter a list reads: its query-string name, its type, its closed values if any."""

    model_config = ConfigDict(extra="forbid")

    param: str = Field(pattern=PARAM_NAME)
    type: ListingType
    values: list[Annotated[str, Field(min_length=1, max_length=MAX_VALUE)]] | None = Field(
        default=None, max_length=MAX_VALUES, description="The closed set, for an enum"
    )


class Listing(BaseModel):
    """A list's declaration as the list contract serves it: its parameters, sorts and search."""

    model_config = ConfigDict(extra="forbid")

    filters: list[ListingFilter] = Field(default_factory=list, max_length=MAX_FIELDS)
    sorts: list[Annotated[str, Field(pattern=SORT_NAME)]] = Field(
        min_length=1, max_length=MAX_SORTS
    )
    q: bool = False


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
        Grammar | SkipJsonSchema[None],
        Field(json_schema_extra=classified("INTERNAL", "The fields, operators and values allowed")),
    ] = None
    listing: Annotated[
        Listing | SkipJsonSchema[None],
        Field(
            json_schema_extra=classified(
                "INTERNAL", "The list's declared parameters and sorts, instead of a grammar"
            )
        ),
    ] = None
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

    @model_validator(mode="after")
    def _one_shape(self) -> Self:
        if (self.grammar is None) == (self.listing is None):
            raise ValueError(ONE_SHAPE)
        return self


class InterpretQueryResponse(ResponseEnvelope):
    """A query that parses against the grammar, what it means in one line, and what it left out."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(max_length=MAX_QUERY)
    explanation: str = Field(max_length=MAX_EXPLANATION)
    unresolved: list[Annotated[str, Field(max_length=MAX_VALUE)]] = Field(max_length=MAX_UNRESOLVED)
    confidence: float = Field(ge=0.0, le=1.0)
    parameters: dict[str, str] = Field(
        default_factory=dict, description="For a list declaration: the parameters, by its names"
    )
    sort: str | None = Field(default=None, description="For a list declaration: a declared sort")
