from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.shop import Product, ShopUser

DEMO_EMAIL = "demo@loopwatch.test"
DEMO_PASSWORD = "demo"


def seed(session: Session) -> None:
    if session.scalar(select(ShopUser.id).limit(1)) is None:
        session.add(ShopUser(email=DEMO_EMAIL, password=DEMO_PASSWORD))
    if session.scalar(select(Product.id).limit(1)) is None:
        session.add_all(
            [
                Product(name="Sensor kit", price_cents=2400),
                Product(name="Fan module", price_cents=1250),
                Product(name="Mounting plate", price_cents=600),
            ]
        )
    session.commit()
