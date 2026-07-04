"""Deterministic configuration for the synthetic e-commerce generator.

All sizing knobs live here so the generator stays pure data — pass a
:class:`GeneratorConfig`, get back datasets. The same ``seed`` is handed
to :mod:`random`, :mod:`faker`, and the per-row timestamp jitter so a
single integer pins every byte of the output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class GeneratorConfig:
    """Sizing + reproducibility knobs for one generator run.

    Attributes
    ----------
    seed:
        Shared RNG seed for ``random.Random``, Faker, and timestamp jitter.
    num_products:
        How many SKUs the catalog contains.
    num_customers:
        How many shoppers the customers table contains.
    num_orders:
        How many top-level orders to emit. Each order carries 1–5 line
        items (chosen uniformly), so the ``order_items`` table is roughly
        ``num_orders * 3`` rows.
    num_clickstream_events:
        How many page / cart / purchase events to emit. Realistic funnels
        have ~10 views per purchase, so defaulting this to ``num_orders *
        10`` from the CLI mimics production conversion rates.
    start_date / end_date:
        Inclusive window the generator spreads event timestamps across.
        Partitioning in later phases keys on ``event_date = date(ts)``.
    locale:
        Faker locale. ``en_US`` keeps the project consistent with the US
        e-commerce persona.
    """

    seed: int = 42
    num_products: int = 500
    num_customers: int = 1_000
    num_orders: int = 2_000
    num_clickstream_events: int = 20_000
    start_date: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    end_date: datetime = datetime(2026, 3, 31, 23, 59, 59, tzinfo=UTC)
    locale: str = "en_US"

    def __post_init__(self) -> None:
        if self.num_products <= 0:
            raise ValueError("num_products must be positive")
        if self.num_customers <= 0:
            raise ValueError("num_customers must be positive")
        if self.num_orders <= 0:
            raise ValueError("num_orders must be positive")
        if self.num_clickstream_events < 0:
            raise ValueError("num_clickstream_events must be non-negative")
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")

    @property
    def window(self) -> timedelta:
        """How wide the event-time window is."""
        return self.end_date - self.start_date
