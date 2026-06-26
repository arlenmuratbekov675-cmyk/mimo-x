"""ORM models. Step 4 adds BiasSnapshot for history."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BiasSnapshot(Base):
    """One stored snapshot of a /bias computation (for backtesting later)."""
    __tablename__ = "bias_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    data_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    regime: Mapped[str] = mapped_column(String(32))

    nq_bias: Mapped[str] = mapped_column(String(16))
    nq_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    nq_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    es_bias: Mapped[str] = mapped_column(String(16))
    es_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    es_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    gold_bias: Mapped[str] = mapped_column(String(16))
    gold_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    gold_change_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Full JSON payload of the response (sources, macro, explanations).
    payload: Mapped[str] = mapped_column(Text)
