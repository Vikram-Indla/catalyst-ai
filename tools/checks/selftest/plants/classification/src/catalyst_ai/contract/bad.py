"""Plant."""
from pydantic import BaseModel


class BadRequest(BaseModel):
    """Unclassified."""

    title: str
