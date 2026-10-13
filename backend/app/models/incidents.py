from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Evidence(Base):
    """One tool result (or detector signal). `ref` is E1, E2, ... within an incident."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), index=True)
    ref: Mapped[str] = mapped_column(String(8))
    tool: Mapped[str] = mapped_column(String(48))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)  # data, never instructions
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hypothesis(Base):
    __tablename__ = "hypothesis"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    cause: Mapped[str] = mapped_column(String(160))  # human label
    cause_key: Mapped[str] = mapped_column(String(32), default="unknown")  # worker_stalled, ...
    confidence: Mapped[float] = mapped_column(Float)
    supporting: Mapped[list] = mapped_column(JSON, default=list)  # evidence refs
    weakening: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Action(Base):
    """state: proposed | awaiting_approval | approved | done | failed | denied | blocked | skipped | rolled_back"""

    __tablename__ = "action"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), index=True)
    type: Mapped[str] = mapped_column(String(32))  # catalog action name
    target: Mapped[str] = mapped_column(String(64))
    risk: Mapped[str] = mapped_column(String(8))  # low | medium | high
    mode: Mapped[str] = mapped_column(String(12))  # auto | approval | blocked
    state: Mapped[str] = mapped_column(String(20), default="proposed")
    rollback: Mapped[str] = mapped_column(Text)  # rollback plan, stored with the action (hard rule 4)
    before: Mapped[dict] = mapped_column(JSON, default=dict)  # state captured before executing, for rollback
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Verification(Base):
    __tablename__ = "verification"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), index=True)
    run_number: Mapped[int] = mapped_column(Integer)
    passed: Mapped[bool] = mapped_column(Boolean)
    ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PastIncident(Base):
    """Seeded and closed incidents used by memory.similar. The embedding is pgvector on
    PostgreSQL and a JSON list elsewhere (tests)."""

    __tablename__ = "past_incident"

    id: Mapped[int] = mapped_column(primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    cause_key: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(24))
    embedding: Mapped[list] = mapped_column(Vector(64).with_variant(JSON(), "sqlite"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    """Created by the open_ticket action and by escalation."""

    __tablename__ = "ticket"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incident.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # ticket | escalation
    note: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(8), default="open")  # open | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
