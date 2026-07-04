"""ecom-aws CLI entry point.

Subcommands are attached with **lazy imports** so a reader on a bare
install never pays the boto3 / faker / pyarrow / pyspark cost just to
run ``ecom-aws --version``. Each handler imports its own module only
when the user actually invokes it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ecom_aws import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecom-aws",
        description="AWS-native e-commerce lakehouse operator CLI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("version", help="Print the installed version and exit.")

    # Phase 2 — synthetic generator.
    gen = subparsers.add_parser(
        "generate",
        help="Emit synthetic e-commerce datasets (catalog, customers, orders, clickstream).",
    )
    gen.add_argument(
        "dataset",
        choices=("all", "catalog", "customers", "orders", "clickstream"),
        help="Which dataset(s) to materialize.",
    )
    gen.add_argument(
        "--out",
        type=Path,
        default=Path("data/bronze/local"),
        help="Output directory (default: data/bronze/local).",
    )
    gen.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42).")
    gen.add_argument("--products", type=int, default=500, help="Catalog SKU count (default: 500).")
    gen.add_argument("--customers", type=int, default=1_000, help="Customer count (default: 1000).")
    gen.add_argument("--orders", type=int, default=2_000, help="Order count (default: 2000).")
    gen.add_argument(
        "--clickstream",
        type=int,
        default=20_000,
        help="Clickstream event count (default: 20000).",
    )

    return parser


def _handle_generate(args: argparse.Namespace) -> int:
    """Lazy-import the generator so the base install stays fast."""
    from ecom_aws.generator import GeneratorConfig, generate_bundle
    from ecom_aws.generator.pipeline import write_bundle

    cfg = GeneratorConfig(
        seed=args.seed,
        num_products=args.products,
        num_customers=args.customers,
        num_orders=args.orders,
        num_clickstream_events=args.clickstream,
    )
    bundle = generate_bundle(cfg)

    if args.dataset == "all":
        written = write_bundle(bundle, args.out)
        for name, path in written.items():
            print(f"  {name:12s} → {path}")
    else:
        # Partial writes still go through write_bundle (same layout) but
        # we filter the printed summary to the user's selection.
        written = write_bundle(bundle, args.out)
        selected = {args.dataset} if args.dataset != "orders" else {"orders", "order_items"}
        for name in selected:
            if name in written:
                print(f"  {name:12s} → {written[name]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    if args.command == "generate":
        return _handle_generate(args)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
