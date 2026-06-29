# Phase 0 — scaffolding, tooling, CI

**Status:** shipped (2026-10-25)

## Goal

Stand up a portfolio-grade repo skeleton so Phases 1-12 can land as
small, focused commits without re-thinking packaging, lint, type-check,
CI, identity, or secrets on each one. Zero application code — every
Phase 0 artifact is a convention.

## What this phase delivers

- **`pyproject.toml`** — hatchling, Python 3.11+, one `ecom-aws` console
  script, and five phase-indexed optional-dependency groups: `dev`,
  `generator`, `aws`, `local-warehouse`, `api`. Each phase installs
  only what it needs; the base install pulls nothing beyond stdlib.
- **`.pre-commit-config.yaml`** — ruff (check + format), mypy on `src/`,
  plus the standard byte-level hygiene set.
- **`.github/workflows/ci.yml`** — two jobs (`lint-and-typecheck` then
  `pytest`) with pip caching, concurrency cancellation, Python 3.11
  pinned. Public repo → unlimited GHA minutes = $0 CI cost forever.
- **`src/ecom_aws/`** — package skeleton with `__version__` and an
  argparse CLI. Later phases attach `generate`, `ingest`, `promote`,
  `orchestrate`, `serve` subcommands via lazy imports.
- **`tests/test_smoke.py`** — 5 Phase 0 tests: package imports, CLI
  version flag, CLI version subcommand, no-args help, console-script
  entry point installed.
- **`LICENSE`** — MIT, 2026 Bapuji Dirisala.
- **`.gitignore`** — Python + Terraform + LocalStack + AWS credentials
  + Lambda build artefacts; `data/`, `lakehouse/`, `warehouse/` and
  all `*.parquet` + `*.duckdb` excluded.
- **`.env.example`** — every env var documented; defaults wire to the
  free local path (LocalStack + DuckDB).

## Design decisions

### Cost model: $0 forever, deployable in one `terraform apply`

Nothing in this repo requires a real AWS account to run end-to-end. The
exact same code paths run against:

- **LocalStack Community** (free) for S3, Lambda, SNS, SQS, Kinesis
  Firehose, API Gateway, EventBridge, DynamoDB.
- **DuckDB** (free, embedded) as the Athena / Redshift Spectrum
  stand-in — Parquet-over-"S3" queries work identically against a
  local filesystem.
- **PySpark + delta-rs** (free, local) as the Glue stand-in for the
  bronze → silver → gold Spark jobs.
- **Python state-machine driver** (free, local) as the Step Functions
  stand-in — same ASL JSON ships, same handler contracts.

Terraform ships for every service as reviewable IaC so a reader with an
AWS account can `terraform apply` and run the identical pipeline on
real AWS. The committed `terraform/` tree is the "production path"
artifact — reviewed by hiring managers, never deployed by me.

### Phase-indexed optional-dependency extras

`[dev]` pulls ruff + mypy + pytest + pre-commit. The other four extras
map one-to-one to the roadmap phases that need them:

- `[generator]` — Phase 2 synthetic data (Faker, pandas, pyarrow).
- `[aws]` — Phase 3+ boto3 + moto + LocalStack client.
- `[local-warehouse]` — Phase 6+ PySpark + delta-spark + delta-rs + DuckDB.
- `[api]` — Phase 11 FastAPI order-status edge service.

A drive-by reader of the repo should NOT have to install 1 GB of Spark
+ Torch wheels to run the Phase 0 smoke tests.

### CLI uses argparse, not click

Lower dependency footprint, same expressiveness for the subcommand
pattern we actually use, consistent with every other repo in the
portfolio. Subcommand modules are lazy-imported from `main()` so the
base install's `ecom-aws --version` stays snappy.

### `moto` for unit tests, LocalStack for integration tests

Two layers:

- **Unit tests** use `moto` fixtures in-process (no containers, pure
  Python mocking). Fast, hermetic, run on every CI push.
- **Integration tests** (marked `localstack`, opt-in via `pytest -m
  localstack`) hit a real LocalStack container. Only run locally when
  the engineer has LocalStack up.

CI deliberately does NOT run LocalStack tests — public-repo GHA is
unlimited but still a shared resource; keeping the default job under
30s matters.

## How to run

```bash
cd ~/Documents/GitHub/ecommerce-aws-platform
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# Verify scaffold:
pytest -q                               # 5 smoke tests, all green
ruff check .                             # no issues
ruff format --check .                    # no formatting drift
mypy src/                                # no type errors
ecom-aws --version                       # prints "ecom-aws 0.1.0"
```

## Gotchas

- **Terraform state must never land in git.** `.gitignore` excludes
  `terraform/.terraform/`, `*.tfstate*`, `*.tfplan`, and all
  `terraform.tfvars` variants. Remote state (S3 + DynamoDB locking)
  gets wired in Phase 1.

- **`.aws/` is excluded from the repo** to prevent accidentally
  committing credentials. Real AWS access goes through
  `~/.aws/credentials` + `AWS_PROFILE` or env vars.

- **LocalStack and Docker vs Colima.** Nike-era note: Docker Desktop
  is banned; use Colima. Everything in this repo assumes the Colima
  context, not Docker Desktop.

## References

- [`../README.md`](../README.md) — 12-phase roadmap + tech stack.
- [`../pyproject.toml`](../pyproject.toml) — authoritative extras list.

## Next phase

**Phase 1** — Terraform baseline. VPC, three S3 buckets (bronze /
silver / gold) with versioning + lifecycle policies, IAM baseline with
least-privilege roles for Lambda / Glue / Firehose, remote state on
S3 + DynamoDB locking. Everything runs green on both LocalStack and
real AWS.
