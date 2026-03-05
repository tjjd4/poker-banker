from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.auth.service import hash_password
from app.config import settings
from app.database import async_session_factory
from app.users.models import User

from app.auth.router import router as auth_router
from app.users.router import router as users_router
from app.tables.router import router as tables_router
from app.transactions.router import router as transactions_router
from app.jackpot.router import router as jackpot_router
from app.reports.router import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 若沒有任何 admin，自動建立預設 admin
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        if result.scalar_one_or_none() is None:
            session.add(
                User(
                    username="admin",
                    password_hash=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
                    display_name="System Admin",
                    role="admin",
                    is_active=True,
                )
            )
            await session.commit()
    yield


app = FastAPI(title="Poker Banker API", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(tables_router, prefix="/api/tables", tags=["tables"])
app.include_router(transactions_router, prefix="/api/transactions", tags=["transactions"])
app.include_router(jackpot_router, prefix="/api/jackpot-pools", tags=["jackpot"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
