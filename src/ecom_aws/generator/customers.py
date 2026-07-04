"""Customer master data generation.

Customers are PII-shaped (name, email, address) but 100% synthetic via
Faker. The ``signed_up_at`` timestamps bunch toward recent dates with a
geometric-looking weighting so most customers are "new" the way real
e-commerce signups skew.
"""

from __future__ import annotations

import random
from datetime import UTC, timedelta

from faker import Faker

from ecom_aws.generator.config import GeneratorConfig


def generate_customers(cfg: GeneratorConfig) -> list[dict]:
    """Build the deterministic customer master table."""
    rng = random.Random(cfg.seed + 1)  # offset so RNG state ≠ catalog's
    Faker.seed(cfg.seed + 1)
    fake = Faker(cfg.locale)

    # Signups span the 2 years before the window so order placement can
    # key off existing customers without racing the catalog timeline.
    signup_floor = cfg.start_date - timedelta(days=730)
    signup_span_s = int((cfg.start_date - signup_floor).total_seconds())

    customers: list[dict] = []
    for i in range(cfg.num_customers):
        # Weight signups toward the recent end of the window via sqrt.
        u = rng.random()
        offset_s = int(signup_span_s * (u**0.5))
        signed_up_at = signup_floor + timedelta(seconds=offset_s)
        if signed_up_at.tzinfo is None:
            signed_up_at = signed_up_at.replace(tzinfo=UTC)

        first = fake.first_name()
        last = fake.last_name()
        # Keep email domain small so dedup/lookup patterns in Phase 6
        # have realistic clash rates.
        email_domain = rng.choice(("example.com", "mailinator.com", "example.org", "test.io"))
        email = f"{first.lower()}.{last.lower()}{i}@{email_domain}"

        state = fake.state_abbr() if rng.random() > 0.03 else None
        customers.append(
            {
                "customer_id": f"CUS{i:06d}",
                "email": email,
                "first_name": first,
                "last_name": last,
                "country": "US",
                "state": state,
                "city": fake.city(),
                "postal_code": fake.postcode(),
                "marketing_opt_in": rng.random() > 0.35,
                "signed_up_at": signed_up_at,
            }
        )
    return customers
