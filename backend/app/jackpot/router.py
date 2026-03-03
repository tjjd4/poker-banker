from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_jackpot_pools():
    pass


@router.post("/")
async def create_jackpot_pool():
    pass


@router.get("/{pool_id}")
async def get_jackpot_pool(pool_id: str):
    pass
