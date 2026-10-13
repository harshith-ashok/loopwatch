import os
import tempfile

# Must be set before app modules read settings: SQLite file DB and fast shop timings.
_tmp = tempfile.mkdtemp(prefix="loopwatch-test-")
os.environ["LOOPWATCH_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["LOOPWATCH_SHOP_PAYMENT_OK_MS"] = "1"
os.environ["LOOPWATCH_SHOP_PAYMENT_SLOW_MS"] = "30"
os.environ["LOOPWATCH_SHOP_PAYMENT_TIMEOUT_MS"] = "60"
os.environ["LOOPWATCH_SHOP_WORKER_TICK_MS"] = "5"
os.environ["LOOPWATCH_JOURNEY_RUNNER_ENABLED"] = "false"  # tests drive runs by hand
os.environ["LOOPWATCH_JOURNEY_ORDER_TIMEOUT_MS"] = "150"
os.environ["LOOPWATCH_DETECTOR_STATE_CHECK_S"] = "1"
os.environ["LOOPWATCH_EDGE_WATCH_ENABLED"] = "false"  # tests tick the simulator by hand
os.environ["LOOPWATCH_SHOP_ACK_HOT_SLOW_MS"] = "40"
os.environ["LOOPWATCH_AGENTS_ENABLED"] = "false"  # tests call investigate() directly
os.environ["LOOPWATCH_AGENTS_SLOW_GATEWAY_MS"] = "20"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.edge.simulator import sim  # noqa: E402
from app.edge.store import store as edge_store  # noqa: E402
from app.shop.faults import state  # noqa: E402


@pytest.fixture
def client():
    Base.metadata.drop_all(get_engine())
    Base.metadata.create_all(get_engine())
    state.reset()
    edge_store.reset()
    sim.__init__()  # fresh healthy node
    with TestClient(app) as c:
        yield c
    state.reset()
