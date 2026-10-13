"""Journey and step definitions. Steps are customer-side HTTP probes of the shop."""

STEP_LABELS = {
    "open_shop": "Open shop",
    "login": "Sign in",
    "add_to_cart": "Add to cart",
    "checkout": "Place order",
    "pay": "Charge card",
    "confirm": "Order confirmed",
    "ack": "Hub acknowledges",
}

JOURNEYS: dict[str, dict[str, object]] = {
    "login": {"label": "Login", "steps": ["open_shop", "login"]},
    "checkout": {"label": "Checkout", "steps": ["open_shop", "login", "add_to_cart", "checkout"]},
    "payment": {"label": "Payment", "steps": ["open_shop", "login", "add_to_cart", "checkout", "pay"]},
    "order": {
        "label": "Order confirmation",
        "steps": ["open_shop", "login", "add_to_cart", "checkout", "pay", "confirm", "ack"],
    },
}
