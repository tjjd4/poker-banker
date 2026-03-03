from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_insurance_events():
    pass
