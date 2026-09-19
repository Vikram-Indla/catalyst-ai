"""Plant."""
from typing import Protocol


class Foo(Protocol):
    """Not a seam."""

    def go(self) -> None:
        """Go."""
