"""Clickstream event generation.

Events form realistic session funnels: a session starts with 1–8 page
views, maybe adds something to cart, occasionally converts to purchase.
Anonymous sessions (no ``customer_id``) make up roughly a third of
traffic — a mix bronze→silver has to handle without blowing up on NULLs.

The emitted event rate is driven by ``cfg.num_clickstream_events`` so the
caller can scale demo size up or down without touching the funnel logic.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, timedelta

from ecom_aws.generator.config import GeneratorConfig

_USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/128.0 Mobile",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128.0",
)

_REFERRERS: tuple[str | None, ...] = (
    "https://www.google.com/",
    "https://www.google.com/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://facebook.com/",
    "https://instagram.com/",
    "https://news.ycombinator.com/",
    None,  # direct
    None,
    None,
)

_PAGE_TEMPLATES: tuple[str, ...] = (
    "/",
    "/catalog",
    "/catalog/{category}",
    "/product/{product_id}",
    "/cart",
    "/checkout",
    "/orders/{order_id}",
    "/account",
)


def _rand_ip(rng: random.Random) -> str:
    # RFC 5737 TEST-NET-1 range so no real IPs leak in.
    return f"192.0.2.{rng.randint(1, 254)}"


def generate_clickstream(
    cfg: GeneratorConfig,
    customers: list[dict],
    products: list[dict],
) -> list[dict]:
    """Build the deterministic clickstream event stream.

    Returns a flat list of event dicts — session structure is implicit via
    ``session_id``. Silver will materialize sessions as a window later.
    """
    rng = random.Random(cfg.seed + 3)
    window_s = int(cfg.window.total_seconds())

    events: list[dict] = []
    while len(events) < cfg.num_clickstream_events:
        session_id = str(uuid.UUID(int=rng.getrandbits(128)))
        session_start_offset = rng.randint(0, window_s)
        session_start = cfg.start_date + timedelta(seconds=session_start_offset)
        if session_start.tzinfo is None:
            session_start = session_start.replace(tzinfo=UTC)
        is_anon = rng.random() < 0.33
        customer = None if is_anon else rng.choice(customers)
        user_agent = rng.choice(_USER_AGENTS)
        referrer = rng.choice(_REFERRERS)
        ip = _rand_ip(rng)

        # 1–8 views, 0–2 add_to_cart, 0–1 purchase
        n_views = rng.randint(1, 8)
        n_cart = rng.randint(0, 2) if rng.random() < 0.35 else 0
        n_purchase = 1 if n_cart > 0 and rng.random() < 0.4 else 0

        plan: list[tuple[str, dict | None]] = [("view", None)] * n_views
        if n_cart:
            plan += [("add_to_cart", rng.choice(products)) for _ in range(n_cart)]
        if n_purchase:
            plan.append(("purchase", rng.choice(products)))

        cursor = session_start
        for event_type, product in plan:
            if len(events) >= cfg.num_clickstream_events:
                break
            # 5–180s between events
            cursor = cursor + timedelta(seconds=rng.randint(5, 180))
            if event_type == "view":
                tpl = rng.choice(_PAGE_TEMPLATES)
                maybe_product = rng.choice(products) if "{product_id}" in tpl else None
                page_url = tpl.format(
                    category=rng.choice(("apparel", "electronics", "home")),
                    product_id=maybe_product["product_id"] if maybe_product else "",
                    order_id="demo",
                )
                pid = maybe_product["product_id"] if maybe_product else None
            else:
                # The "view" branch above sets product to None; the plan
                # guarantees "add_to_cart" / "purchase" always carry a product.
                assert product is not None
                page_url = f"/product/{product['product_id']}"
                pid = product["product_id"]

            events.append(
                {
                    "event_id": str(uuid.UUID(int=rng.getrandbits(128))),
                    "session_id": session_id,
                    "customer_id": customer["customer_id"] if customer else None,
                    "event_ts": cursor,
                    "event_type": event_type,
                    "page_url": page_url,
                    "product_id": pid,
                    "referrer": referrer,
                    "user_agent": user_agent,
                    "ip_address": ip,
                    "event_date": cursor.date(),
                }
            )

    # Clip to the exact requested count in case the last session overfilled.
    return events[: cfg.num_clickstream_events]
