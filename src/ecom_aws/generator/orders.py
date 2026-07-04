"""Order + line-item generation.

Each order references a real customer and 1–5 real products. Totals are
computed deterministically from the sampled unit prices + quantities so
the Phase 6 silver cast and the Phase 7 gold aggregates have a known
ground truth to test against.
"""

from __future__ import annotations

import random
from datetime import UTC, timedelta
from decimal import ROUND_HALF_UP, Decimal

from ecom_aws.generator.config import GeneratorConfig

_STATUS_WEIGHTS: dict[str, float] = {
    "placed": 10.0,
    "paid": 65.0,
    "shipped": 15.0,
    "delivered": 8.0,
    "cancelled": 2.0,
}

_PAYMENT_METHODS: tuple[str, ...] = (
    "credit_card",
    "debit_card",
    "paypal",
    "gift_card",
    "apple_pay",
)


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    keys = list(weights.keys())
    vals = list(weights.values())
    return rng.choices(keys, weights=vals, k=1)[0]


def generate_orders(
    cfg: GeneratorConfig,
    customers: list[dict],
    products: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Return ``(orders, order_items)`` lists with full referential integrity.

    Both tables use string IDs; totals are ``Decimal`` so Parquet writes
    land in the fixed-scale columns pinned by :mod:`.schemas`.
    """
    rng = random.Random(cfg.seed + 2)
    window_s = int(cfg.window.total_seconds())

    orders: list[dict] = []
    items: list[dict] = []

    for i in range(cfg.num_orders):
        customer = rng.choice(customers)
        n_items = rng.randint(1, 5)
        chosen = rng.sample(products, k=min(n_items, len(products)))

        placed_at = cfg.start_date + timedelta(seconds=rng.randint(0, window_s))
        if placed_at.tzinfo is None:
            placed_at = placed_at.replace(tzinfo=UTC)
        order_id = f"ORD{i:08d}"

        subtotal = Decimal("0")
        for j, product in enumerate(chosen):
            qty = rng.randint(1, 3)
            unit_price = Decimal(product["list_price_usd"])
            # Occasional 10–30% promo discount on individual lines.
            if rng.random() < 0.18:
                discount = Decimal(str(round(rng.uniform(0.10, 0.30), 2)))
                unit_price = _round(unit_price * (Decimal("1") - discount))
            line_total = _round(unit_price * qty)
            items.append(
                {
                    "order_item_id": f"{order_id}-{j:02d}",
                    "order_id": order_id,
                    "product_id": product["product_id"],
                    "quantity": qty,
                    "unit_price_usd": unit_price,
                    "line_total_usd": line_total,
                }
            )
            subtotal += line_total

        subtotal = _round(subtotal)
        tax = _round(subtotal * Decimal("0.0825"))  # flat demo rate
        shipping = Decimal("0.00") if subtotal >= Decimal("50.00") else Decimal("5.99")
        total = _round(subtotal + tax + shipping)

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer["customer_id"],
                "placed_at": placed_at,
                "status": _weighted_choice(rng, _STATUS_WEIGHTS),
                "payment_method": rng.choice(_PAYMENT_METHODS),
                "ship_country": customer["country"],
                "ship_state": customer["state"],
                "subtotal_usd": subtotal,
                "tax_usd": tax,
                "shipping_usd": shipping,
                "total_usd": total,
                "event_date": placed_at.date(),
            }
        )

    return orders, items
