"""Plant."""
from fastapi import APIRouter

router = APIRouter()


@router.post("/x")
async def run(flag: bool) -> int:
    """Branches."""
    if flag:
        return 1
    return 0
