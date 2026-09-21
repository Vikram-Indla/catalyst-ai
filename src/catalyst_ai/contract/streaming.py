"""The frames of a streamed operation: typed, and exactly one terminal frame ends every stream.

`delta` carries text as it arrives; `citation` a source the reply rests on; `usage` comes once;
then `done` with the validated response, or `error` with the envelope. A stream that closes
without a terminal frame is a defect the backend treats as `ai.provider.unavailable`.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.assistant import TurnResponse, TurnSource
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorEnvelope

MAX_DELTA = 4_000


class DeltaFrame(BaseModel):
    """A piece of the reply's prose, in order; the joined deltas are the reply of `done`."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["delta"] = "delta"
    text: str = Field(max_length=MAX_DELTA)


class CitationFrame(BaseModel):
    """One source the reply rests on, sent once it is known."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["citation"] = "citation"
    source: TurnSource


class UsageFrame(BaseModel):
    """The turn's tokens, cost and latency; sent once, before the terminal frame."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["usage"] = "usage"
    usage: Usage


class DoneFrame(BaseModel):
    """The terminal frame of a stream that succeeded: the whole validated response."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["done"] = "done"
    result: TurnResponse


class ErrorFrame(BaseModel):
    """The terminal frame of a stream that failed: the same envelope every operation returns."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["error"] = "error"
    error: ErrorEnvelope


Frame = Annotated[
    DeltaFrame | CitationFrame | UsageFrame | DoneFrame | ErrorFrame, Field(discriminator="kind")
]


class StreamEnvelope(BaseModel):
    """The documented shape of one server-sent event's data; the event name equals `kind`."""

    model_config = ConfigDict(extra="forbid")

    frame: Frame
