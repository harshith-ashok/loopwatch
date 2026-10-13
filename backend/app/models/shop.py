from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ShopUser(Base):
    __tablename__ = "shop_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    password: Mapped[str] = mapped_column(String(120))  # demo only, never real credentials


class Product(Base):
    __tablename__ = "product"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    price_cents: Mapped[int] = mapped_column(Integer)


class CartItem(Base):
    __tablename__ = "cart_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("shop_user.id"), index=True)
    session_token: Mapped[str] = mapped_column(String(64), index=True)  # cart belongs to one login session
    product_id: Mapped[int] = mapped_column(ForeignKey("product.id"))
    qty: Mapped[int] = mapped_column(Integer, default=1)


class ShopOrder(Base):
    """status: pending_payment -> paid -> confirmed (worker) | payment_failed"""

    __tablename__ = "shop_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("shop_user.id"), index=True)
    total_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="pending_payment", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("shop_order.id"), index=True)
    gateway: Mapped[str] = mapped_column(String(24))  # primary | fallback
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))  # captured | failed
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShopLog(Base):
    """Structured shop log lines; searched later by the logs.search agent tool."""

    __tablename__ = "shop_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    level: Mapped[str] = mapped_column(String(8))
    component: Mapped[str] = mapped_column(String(32), index=True)
    event: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(String(400))
    fields: Mapped[dict] = mapped_column(JSON, default=dict)
