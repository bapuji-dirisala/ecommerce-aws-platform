"""Product catalog generation.

The catalog is deterministic and small on purpose: ~500 SKUs across a
handful of categories so downstream aggregations have realistic
cardinality without blowing up the Parquet footprint. Prices follow a
log-normal shape so a few hero items anchor the gross-merchandise tail.
"""

from __future__ import annotations

import random
from datetime import UTC, timedelta
from decimal import ROUND_HALF_UP, Decimal

from faker import Faker

from ecom_aws.generator.config import GeneratorConfig

# Static distribution kept here (not in config) so prod-shape stays
# consistent across runs — only the seed should drive variation.
_CATEGORIES: tuple[str, ...] = (
    "Apparel",
    "Footwear",
    "Electronics",
    "Home",
    "Beauty",
    "Grocery",
    "Toys",
    "Outdoor",
    "Books",
    "Accessories",
)

_BRANDS_BY_CATEGORY: dict[str, tuple[str, ...]] = {
    "Apparel": ("Nordlys", "Ember", "Sable", "Rowan", "Marin"),
    "Footwear": ("Trekker", "Pace", "Loft", "Current"),
    "Electronics": ("Orbis", "Volt", "Kineo", "Flux"),
    "Home": ("Hearth", "Prairie", "Linden", "Quill"),
    "Beauty": ("Glow", "Petal", "Milu", "Aster"),
    "Grocery": ("Field", "Harvest", "Stone", "River"),
    "Toys": ("Spool", "Kite", "Bumble"),
    "Outdoor": ("Ridge", "Alpine", "Wayfare"),
    "Books": ("Press", "Lantern", "Codex"),
    "Accessories": ("Clasp", "Thread", "Loop"),
}


def _round(amount: Decimal) -> Decimal:
    """Round to cents with banker-safe HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def generate_products(cfg: GeneratorConfig) -> list[dict]:
    """Build the deterministic product catalog.

    Returns a list of dicts (not DataFrames) so the result stays trivially
    serializable for pyarrow / JSON / unit test assertions.
    """
    rng = random.Random(cfg.seed)
    Faker.seed(cfg.seed)
    fake = Faker(cfg.locale)

    products: list[dict] = []
    # Spread product creation times across the 365d before the generator
    # window so "customers signed up after a product was already listed"
    # holds without extra bookkeeping.
    catalog_start = cfg.start_date - timedelta(days=365)

    for i in range(cfg.num_products):
        category = rng.choice(_CATEGORIES)
        brand = rng.choice(_BRANDS_BY_CATEGORY[category])
        # Log-normal-ish price distribution: a few expensive hero items,
        # a long tail of everyday goods.
        base_price = Decimal(str(round(rng.lognormvariate(2.5, 0.9), 2)))
        base_price = max(Decimal("1.99"), min(Decimal("999.99"), base_price))
        list_price = _round(base_price)
        # Margin varies ±5% around 40% so cost rounds cleanly.
        margin = Decimal(str(round(rng.uniform(0.35, 0.45), 3)))
        cost = _round(list_price * (Decimal("1") - margin))
        created_offset_days = rng.randint(0, 365)
        created_at = catalog_start + timedelta(
            days=created_offset_days,
            hours=rng.randint(0, 23),
            minutes=rng.randint(0, 59),
        )
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)

        products.append(
            {
                "product_id": f"PRD{i:06d}",
                "sku": f"{category[:3].upper()}-{brand[:3].upper()}-{i:05d}",
                "name": f"{brand} {fake.word().title()} {category[:-1] if category.endswith('s') else category}",
                "category": category,
                "brand": brand,
                "list_price_usd": list_price,
                "cost_usd": cost,
                "in_stock": rng.random() > 0.08,  # ~92% in stock
                "created_at": created_at,
            }
        )
    return products
