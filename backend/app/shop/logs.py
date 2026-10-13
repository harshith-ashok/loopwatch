import logging
from typing import Any

from app.core.db import get_sessionmaker
from app.models.shop import ShopLog

_log = logging.getLogger("shop")


def shop_log(
    component: str, event: str, message: str, level: str = "INFO", **fields: Any
) -> None:
    """Write one structured line to stdout and to the shop_log table."""
    _log.log(logging.getLevelName(level), message, extra={"fields": {"component": component, "event": event, **fields}})
    try:
        with get_sessionmaker()() as session:
            session.add(
                ShopLog(level=level, component=component, event=event, message=message[:400], fields=fields)
            )
            session.commit()
    except Exception:  # logging must never break the shop
        _log.exception("could not persist shop log")
