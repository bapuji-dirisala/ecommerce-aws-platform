"""ecom-aws CLI entry point.

Phase 0 ships the skeleton; later phases attach subcommands via lazy
imports so a reader on the base install never pays the boto3 / faker /
pyspark import cost on `ecom-aws --version`.
"""

from __future__ import annotations

import argparse
import sys

from ecom_aws import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ecom-aws",
        description="AWS-native e-commerce lakehouse operator CLI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("version", help="Print the installed version and exit.")

    # Phase 2 will attach `generate` (synthetic data), Phase 3+ `ingest`,
    # Phase 7 `promote` (silver → gold), Phase 8 `orchestrate` (Step
    # Functions local driver), Phase 11 `serve` (FastAPI). Keep the
    # skeleton empty-but-valid so `ecom-aws --help` works at Phase 0.
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "version":
        print(__version__)
        return 0
    _build_parser().print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
