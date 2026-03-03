from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.tables.router import router as tables_router
from app.transactions.router import router as transactions_router
from app.insurance.router import router as insurance_router
from app.jackpot.router import router as jackpot_router
from app.reports.router import router as reports_router

app = FastAPI(title="Poker Banker API")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(tables_router, prefix="/api/tables", tags=["tables"])
app.include_router(transactions_router, prefix="/api/transactions", tags=["transactions"])
app.include_router(insurance_router, prefix="/api/insurance", tags=["insurance"])
app.include_router(jackpot_router, prefix="/api/jackpot-pools", tags=["jackpot"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
