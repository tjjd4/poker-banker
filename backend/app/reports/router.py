from fastapi import APIRouter

router = APIRouter()


@router.get("/daily")
async def daily_report():
    pass


@router.get("/table/{table_id}")
async def table_report(table_id: str):
    pass
