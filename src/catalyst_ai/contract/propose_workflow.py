"""The propose_workflow operation: a described process becomes a scheme the backend validates."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class Status(BaseModel):
    """One status of the scheme: its key, label, category and role."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    label: str = Field(min_length=1, max_length=MAX_LABEL)
    category: StatusCategory
    initial: bool = False
    terminal: bool = False
    sort_order: int = Field(ge=0, le=MAX_STATUSES)


class Transition(BaseModel):
    """One allowed move; `from_key` null means from any status; guards name engine conditions."""

    model_config = ConfigDict(extra="forbid")

    from_key: str | None = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    to_key: str = Field(pattern=KEY_SHAPE, max_length=MAX_KEY)
    kind: TransitionKind
    guards: list[str] = Field(default_factory=list, max_length=MAX_GUARDS_PER_TRANSITION)
    requires_approval: bool = False
    reason_code: str | None = Field(default=None, pattern=KEY_SHAPE, max_length=MAX_KEY)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE)


class Scheme(BaseModel):
    """A whole scheme: the statuses and the transitions between them."""

    model_config = ConfigDict(extra="forbid")

    statuses: list[Status] = Field(max_length=MAX_STATUSES)
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
