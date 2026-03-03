import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JackpotPool(Base):
    __tablename__ = "jackpot_pools"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    banker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class JackpotTrigger(Base):
    __tablename__ = "jackpot_triggers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    pool_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("jackpot_pools.id"), nullable=False
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tables.id"), nullable=False
    )
    winner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    hand_description: Mapped[str] = mapped_column(String(200), nullable=False)
    payout_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    pool_balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    triggered_by: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
