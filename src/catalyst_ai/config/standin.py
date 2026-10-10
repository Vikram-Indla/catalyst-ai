"""The stand-in switch: development may answer without a model, and nowhere else may.

On, the process answers its model calls with the development stand-in (`providers/standin.py`):
fixed, marked text, no model, nothing leaving the machine. The settings refuse it outside
development (`config/deployed.py`), so a deployed process can never serve stand-in text.
"""

from typing import Annotated

from pydantic import BaseModel, Field


class StandInSwitch(BaseModel):
    """The one switch; `Settings` inherits it, so it is a top-level variable."""

    provider_stand_in: Annotated[
        bool,
        Field(
            description=(
                "PUBLIC · Answer model calls with the development stand-in: fixed, marked text, no "
                "model; development only"
            )
        ),
    ] = False
