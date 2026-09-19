"""Plant: stages out of order."""


async def run(request: str) -> str:
    """Out of order."""
    value = await call(request)
    value = await parse(value)
    return await postprocess(value)


async def parse(value: str) -> str:
    """Parse."""
    return value


async def call(value: str) -> str:
    """Call."""
    return value


async def postprocess(value: str) -> str:
    """Post."""
    return value
