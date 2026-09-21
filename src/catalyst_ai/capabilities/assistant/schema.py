"""What a completion must look like: the reply's prose, a line of three dashes, a JSON tail.

The prose streams; the tail never does. The tail carries what cannot be streamed: whether the
sources answered the question, and one sentence of rationale for the record.
"""

import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catalyst_ai.platform.pipeline import hold_back

MARKER = "\n---\n"
MAX_RATIONALE_CHARS = 300
NO_TAIL = "the completion has no tail"


class Tail(BaseModel):
    """The structured end of a completion."""

    model_config = ConfigDict(extra="forbid")

    not_found: bool = False
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


@dataclass(frozen=True)
class Output:
    """What a valid completion carries once split: the prose and the tail."""

    prose: str
    tail: Tail


def visible(text: str) -> str:
    """Return the part of a growing completion that may be shown: the prose before the marker."""
    return hold_back(text, MARKER)


def split(text: str) -> tuple[str, Tail]:
    """Return the prose and the parsed tail; raise ValueError when the tail is missing or bad."""
    cut = text.find(MARKER)
    if cut < 0:
        raise ValueError(NO_TAIL)
    try:
        tail = Tail.model_validate(json.loads(text[cut + len(MARKER) :]))
    except (ValidationError, ValueError) as error:
        raise ValueError(str(error)) from error
    return text[:cut].strip(), tail
