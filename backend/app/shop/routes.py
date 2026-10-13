"""Demo target shop. Deliberately simple; this is what Loopwatch watches and we break."""
import asyncio
import random
import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.models.shop import CartItem, Payment, Product, ShopOrder, ShopUser
from app.edge.store import store as edge_store
from app.shop.faults import state
from app.shop.logs import shop_log
from app.shop.worker import worker

router = APIRouter(prefix="/shop", tags=["shop"])

_sessions: dict[str, int] = {}  # token -> user id
_rng = random.Random()


class LoginIn(BaseModel):
    email: str
    password: str


class CartAdd(BaseModel):
    product_id: int
    qty: int = 1


class ChargeIn(BaseModel):
    order_id: int


class Auth(BaseModel):
    user: ShopUser
    token: str

    model_config = {"arbitrary_types_allowed": True}


def current_auth(
    session: Annotated[Session, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> Auth:
    token = (authorization or "").removeprefix("Bearer ").strip()
    user = session.get(ShopUser, _sessions.get(token, -1))
    if user is None:
        raise HTTPException(401, "not logged in")
    return Auth(user=user, token=token)


User = Annotated[Auth, Depends(current_auth)]
Db = Annotated[Session, Depends(get_session)]


@router.post("/login")
def login(body: LoginIn, session: Db) -> dict[str, str]:
    user = session.scalar(select(ShopUser).where(ShopUser.email == body.email))
    if user is None or user.password != body.password:
        shop_log("auth", "login_failed", "login rejected", level="WARNING", email=body.email)
        raise HTTPException(401, "invalid credentials")
    token = secrets.token_hex(16)
    _sessions[token] = user.id
    shop_log("auth", "login_ok", "login ok", user_id=user.id)
    return {"token": token}


@router.get("/products")
def products(session: Db) -> list[dict[str, object]]:
    return [
        {"id": p.id, "name": p.name, "price_cents": p.price_cents}
        for p in session.scalars(select(Product))
    ]


@router.post("/cart/items")
def add_to_cart(body: CartAdd, user: User, session: Db) -> dict[str, int]:
    if session.get(Product, body.product_id) is None:
        raise HTTPException(404, "unknown product")
    session.add(
        CartItem(user_id=user.user.id, session_token=user.token, product_id=body.product_id, qty=max(1, body.qty))
    )
    session.commit()
    count = len(session.scalars(select(CartItem.id).where(CartItem.session_token == user.token)).all())
    return {"items": count}


@router.post("/checkout")
def checkout(user: User, session: Db) -> dict[str, int]:
    rows = session.execute(
        select(CartItem, Product).join(Product, Product.id == CartItem.product_id).where(CartItem.session_token == user.token)
    ).all()
    if not rows:
        raise HTTPException(409, "cart is empty")
    total = sum(item.qty * product.price_cents for item, product in rows)
    order = ShopOrder(user_id=user.user.id, total_cents=total, status="pending_payment")
    session.add(order)
    session.execute(delete(CartItem).where(CartItem.session_token == user.token))
    session.commit()
    shop_log("checkout", "order_created", f"order {order.id} created", order_id=order.id, total_cents=total)
    return {"order_id": order.id, "total_cents": total}


async def _charge(gateway: str, body: ChargeIn, session: Session) -> dict[str, object]:
    cfg = get_settings()
    order = session.get(ShopOrder, body.order_id)
    if order is None:
        raise HTTPException(404, "unknown order")
    if order.status != "pending_payment":
        raise HTTPException(409, f"order is {order.status}")

    degraded = gateway == "primary" and state.timeout
    failed = False
    if gateway == "primary" and state.slow and not degraded:
        latency = cfg.shop_payment_slow_ms
    elif degraded:
        forced = state.timeout_first
        state.timeout_first = False
        if forced or _rng.random() < cfg.shop_timeout_error_rate:
            latency, failed = cfg.shop_payment_timeout_ms, True
        else:
            latency = cfg.shop_payment_slow_ms
    else:
        latency = cfg.shop_payment_ok_ms
    await asyncio.sleep(latency / 1000)

    session.add(
        Payment(
            order_id=order.id,
            gateway=gateway,
            amount_cents=order.total_cents,
            status="failed" if failed else "captured",
            latency_ms=latency,
            created_at=datetime.now(timezone.utc),  # explicit: the stuck-order rule needs sub-second accuracy
        )
    )
    if failed:
        session.commit()
        shop_log(
            f"payments-{gateway}", "gateway_timeout", f"gateway timeout after {latency} ms",
            level="ERROR", order_id=order.id, gateway=gateway, latency_ms=latency,
        )
        raise HTTPException(504, "payment gateway timeout")

    order.status = "paid"
    session.commit()
    worker.enqueue(order.id)
    shop_log(
        f"payments-{gateway}", "payment_captured", f"payment captured for order {order.id}",
        order_id=order.id, gateway=gateway, latency_ms=latency,
    )
    return {"order_id": order.id, "gateway": gateway, "status": "captured", "latency_ms": latency}


@router.post("/payments-primary/charge")
async def charge_primary(body: ChargeIn, session: Db) -> dict[str, object]:
    return await _charge("primary", body, session)


@router.post("/payments-fallback/charge")
async def charge_fallback(body: ChargeIn, session: Db) -> dict[str, object]:
    return await _charge("fallback", body, session)


@router.post("/pay")
async def pay(body: ChargeIn, session: Db) -> dict[str, object]:
    """Pays through whichever gateway is currently routed (switch_endpoint flips this)."""
    return await _charge(state.payment_route, body, session)


@router.get("/orders/{order_id}")
def order_confirmation(order_id: int, session: Db) -> dict[str, object]:
    order = session.get(ShopOrder, order_id)
    if order is None:
        raise HTTPException(404, "unknown order")
    return {"order_id": order.id, "status": order.status, "total_cents": order.total_cents}


@router.post("/orders/{order_id}/ack")
async def acknowledge_order(order_id: int, session: Db) -> dict[str, object]:
    """The fulfillment hub (edge node) acknowledges a confirmed order. A hot hub is slow and an
    offline hub fails; with ack_route=manual the ack goes to a manual queue instead."""
    cfg = get_settings()
    order = session.get(ShopOrder, order_id)
    if order is None:
        raise HTTPException(404, "unknown order")
    if order.status != "confirmed":
        raise HTTPException(409, f"order is {order.status}")
    if state.ack_route == "manual":
        shop_log("hub", "ack_manual_queue", f"order {order_id} acknowledged via manual queue", order_id=order_id)
        return {"order_id": order_id, "acknowledged_by": "manual_queue"}
    node = edge_store.status(cfg.edge_node)
    if not node.online:
        shop_log("hub", "hub_unreachable", f"hub {cfg.edge_node} unreachable", level="ERROR", order_id=order_id)
        raise HTTPException(503, "fulfillment hub unreachable")
    if node.temp_c is not None and node.temp_c > cfg.edge_temp_limit_c:
        await asyncio.sleep(cfg.shop_ack_hot_slow_ms / 1000)
        shop_log("hub", "hub_slow", f"hub {cfg.edge_node} acked slowly", level="WARNING",
                 order_id=order_id, temp_c=node.temp_c)
    return {"order_id": order_id, "acknowledged_by": "hub"}


@router.get("/state")
def shop_state() -> dict[str, object]:
    return {
        "queue_depth": worker.queue_depth,
        "consumers": worker.consumers,
        "payment_route": state.payment_route,
        "ack_route": state.ack_route,
        "faults": {"stall": state.stall, "timeout": state.timeout},
    }
