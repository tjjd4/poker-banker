import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InsuranceEvent(Base):
    __tablename__ = "insurance_events"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    table_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tables.id"), nullable=False
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False
    )
    seller_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    buyer_hand: Mapped[Any] = mapped_column(JSON, nullable=False)
    opponent_hand: Mapped[Any] = mapped_column(JSON, nullable=False)
    community_cards: Mapped[Any] = mapped_column(JSON, nullable=False)
    outs: Mapped[int] = mapped_column(Integer, nullable=False)
    win_probability: Mapped[float] = mapped_column(Float, nullable=False)
    odds: Mapped[float] = mapped_column(Float, nullable=False)
    insured_amount: Mapped[int] = mapped_column(Integer, default=0)
    payout_amount: Mapped[int] = mapped_column(Integer, default=0)
    is_hit: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
