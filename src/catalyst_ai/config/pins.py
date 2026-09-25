"""The model pins: each alias may name another of the register's priced ids, per environment.

Unset, an alias resolves to the register's row. Set, the provider checks the value against the
register when it is built, before the process serves, and refuses an id the register does not
price for that alias's class, naming the setting (`D-064`). A model is thereby swapped without
code only among rows that carry a price and an eval run. The ids themselves live only in the
register (`ARCH-005 §2`); configuration carries the choice.
"""

from typing import Annotated

from pydantic import BaseModel, Field

MAX_MODEL_ID = 64


class ModelPins(BaseModel):
    """The four pins; `Settings` inherits them, so each is a top-level variable."""

    model_text_default: Annotated[
        str | None,
        Field(
            max_length=MAX_MODEL_ID,
            description="PUBLIC · The model text-default resolves to; unset, the register's",
        ),
    ] = None
    model_text_fast: Annotated[
        str | None,
        Field(
            max_length=MAX_MODEL_ID,
            description="PUBLIC · The model text-fast resolves to; unset, the register's",
        ),
    ] = None
    model_grader_default: Annotated[
        str | None,
        Field(
            max_length=MAX_MODEL_ID,
            description="PUBLIC · The model the eval grader uses; unset, the register's",
        ),
    ] = None
    model_embed_default: Annotated[
        str | None,
        Field(
            max_length=MAX_MODEL_ID,
            description="PUBLIC · The index's embedding model; unset, the register's",
        ),
    ] = None
