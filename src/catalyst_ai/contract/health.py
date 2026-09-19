"""Liveness and readiness responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class LiveResponse(BaseModel):
    """Return the process is up."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["live"]


class ReadyResponse(BaseModel):
    """Return the process can serve: configuration loaded and every dependency it needs answers."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "not_ready"]
    checks: dict[str, bool]
