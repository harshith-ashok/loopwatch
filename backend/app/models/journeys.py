from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

TERMINAL_STATES = {"resolved", "mitigated", "escalated", "false_positive", "cancelled"}


class JourneyRun(Base):
    __tablename__ = "journey_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    journey: Mapped[str] = mapped_column(String(24), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ok: Mapped[bool] = mapped_column(Boolean)
    total_ms: Mapped[int] = mapped_column(Integer)
    failed_step: Mapped[str | None] = mapped_column(String(24), nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Incident(Base):
    """Phase 2 holds the detector's view. Stages, evidence and actions arrive in Phase 3+."""

    __tablename__ = "incident"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    journey: Mapped[str] = mapped_column(String(24), index=True)
    state: Mapped[str] = mapped_column(String(24), default="investigating", index=True)
    rule: Mapped[str] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(32), index=True)
    signals: Mapped[dict] = mapped_column(JSON, default=dict)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)  # seeded sample data; excluded from scoring
