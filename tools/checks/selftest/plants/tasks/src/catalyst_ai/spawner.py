"""Plant."""
import asyncio


async def work() -> None:
    """Work."""


async def spawn() -> None:
    """Fires and forgets."""
    asyncio.create_task(work())
