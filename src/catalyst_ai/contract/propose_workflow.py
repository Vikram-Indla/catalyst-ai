"""The propose_workflow operation: a described process becomes a scheme the backend validates."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.config import JsonDict

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_DESCRIPTION = 4_000
MAX_KEY = 64
MAX_LABEL = 120
MAX_RATIONALE = 300
MAX_STATUSES = 25
MAX_TRANSITIONS = 100
MAX_GUARDS = 40
MAX_GUARDS_PER_TRANSITION = 5
MAX_LANGUAGE = 16
KEY_SHAPE = r"^[a-z][a-z0-9_]{0,63}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

EmptyReason = Literal["description_too_vague"]
CATEGORIES_MISSING = "allowed_categories must include todo and done"
CATEGORIES_REPEAT = "allowed_categories repeats a category"
GUARDS_REPEAT = "guard_vocabulary repeats a guard"
NAME_REQUIRED = "a status needs a name"
ORDER_REQUIRED = "a status needs an order"


def deprecated() -> JsonDict:
    """Return the schema extra that marks a mirror field the next minor removes."""
    return {"deprecated": True, "description": "Read the engine's word instead; removed at 1.2.0"}


class StatusCategory(StrEnum):
    """The three categories every engine status falls into."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class TransitionKind(StrEnum):
    """What a transition means to the engine; `backward`, `reject` and `reopen` need a reason."""

    FORWARD = "forward"
    BACKWARD = "backward"
    REOPEN = "reopen"
    CANCEL = "cancel"
    REJECT = "reject"
    DEFER = "defer"
    EXCEPTION = "exception"


class StatusBase(BaseModel):
    """One status of the scheme: its key, name, category, whether it is the initial one, its order.

    `terminal` is informative: the engine treats `done` as the resting class and lets a reopen
    move out of it.
    """

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    name: str = Field(min_length=1, max_length=MAX_LABEL)
    category: StatusCategory
    initial: bool = False
    terminal: bool = False
    order: int = Field(ge=0, le=MAX_STATUSES)


class Status(StatusBase):
    """A proposed status; `label` and `sort_order` repeat `name` and `order` until 1.2.0."""

    label: str = Field(min_length=1, max_length=MAX_LABEL, json_schema_extra=deprecated())
    sort_order: int = Field(ge=0, le=MAX_STATUSES, json_schema_extra=deprecated())


class ExistingStatus(BaseModel):
    """A status of the scheme to extend, under either spelling; `name` and `order` are read."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    name: str | None = Field(default=None, min_length=1, max_length=MAX_LABEL)
    label: str | None = Field(
        default=None, min_length=1, max_length=MAX_LABEL, json_schema_extra=deprecated()
    )
    category: StatusCategory
    initial: bool = False
    terminal: bool = False
    order: int | None = Field(default=None, ge=0, le=MAX_STATUSES)
    sort_order: int | None = Field(
        default=None, ge=0, le=MAX_STATUSES, json_schema_extra=deprecated()
    )

    @model_validator(mode="after")
    def _one_spelling(self) -> Self:
        if self.name is None and self.label is None:
            raise ValueError(NAME_REQUIRED)
        if self.order is None and self.sort_order is None:
            raise ValueError(ORDER_REQUIRED)
        self.name = self.name if self.name is not None else self.label
        self.order = self.order if self.order is not None else self.sort_order
        return self


class TransitionBase(BaseModel):
    """One allowed move; a null `from_key` means from any status; guards are the engine's.

    The engine expands a null `from_key` into one transition per status; its one guard today is
    `requires_reason`; a reason code where the kind needs one.
    """

    model_config = ConfigDict(extra="forbid")

    from_key: str | None = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    to_key: str = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    kind: TransitionKind
    guards: list[str] = Field(default_factory=list, max_length=MAX_GUARDS_PER_TRANSITION)
    reason_code: str | None = Field(default=None, pattern=KEY_SHAPE, max_length=MAX_KEY)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE)


class Transition(TransitionBase):
    """A transition as sent and returned; `requires_approval` is always false until 1.2.0."""

    requires_approval: bool = Field(default=False, json_schema_extra=deprecated())


class Scheme(BaseModel):
    """The scheme to extend: its statuses under either spelling and its transitions."""

    model_config = ConfigDict(extra="forbid")

    statuses: list[ExistingStatus] = Field(max_length=MAX_STATUSES)
    transitions: list[Transition] = Field(max_length=MAX_TRANSITIONS)


class ProposeWorkflowRequest(RequestEnvelope):
    """The process in words, what the engine allows, and the scheme to extend when there is one."""

    model_config = ConfigDict(extra="forbid")

    description: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_DESCRIPTION,
            json_schema_extra=classified("CONFIDENTIAL", "The process as the admin describes it"),
        ),
    ]
    item_type: Annotated[
        str | None,
        Field(
            max_length=MAX_KEY,
            json_schema_extra=classified("INTERNAL", "The work item type the scheme is for"),
        ),
    ] = None
    allowed_categories: Annotated[
        list[StatusCategory],
        Field(
            min_length=2,
            max_length=len(StatusCategory),
            json_schema_extra=classified(
                "INTERNAL", "The categories the engine allows; must include todo and done"
            ),
        ),
    ] = Field(default_factory=lambda: list(StatusCategory))
    guard_vocabulary: Annotated[
        list[str],
        Field(
            max_length=MAX_GUARDS,
            json_schema_extra=classified(
                "INTERNAL", "The guard names the engine knows; a proposal uses no other"
            ),
        ),
    ] = Field(default_factory=list)
    existing: Annotated[
        Scheme | None,
        Field(
            json_schema_extra=classified(
                "INTERNAL", "The scheme to extend; every status of it stays in the proposal"
            )
        ),
    ] = None
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag of labels and rationales"),
        ),
    ] = None

    @model_validator(mode="after")
    def _categories_span_the_scheme(self) -> Self:
        allowed = set(self.allowed_categories)
        if {StatusCategory.TODO, StatusCategory.DONE} - allowed:
            raise ValueError(CATEGORIES_MISSING)
        if len(allowed) != len(self.allowed_categories):
            raise ValueError(CATEGORIES_REPEAT)
        if len(set(self.guard_vocabulary)) != len(self.guard_vocabulary):
            raise ValueError(GUARDS_REPEAT)
        return self


class ProposeWorkflowResponse(ResponseEnvelope):
    """The scheme proposed, or nothing with its reason; a confidence the backend may read."""

    model_config = ConfigDict(extra="forbid")

    statuses: list[Status]
    transitions: list[Transition]
    empty_reason: EmptyReason | None
    confidence: float = Field(ge=0.0, le=1.0)
