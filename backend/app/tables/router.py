from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def list_tables():
    pass


@router.post("/")
async def create_table():
    pass


@router.get("/{table_id}")
async def get_table(table_id: str):
    pass


@router.post("/{table_id}/seats")
async def seat_player(table_id: str):
    pass


@router.post("/{table_id}/transactions")
async def create_transaction(table_id: str):
    pass


@router.post("/{table_id}/insurance")
async def create_insurance_event(table_id: str):
    pass
