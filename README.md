# ecommerce-aws-platform

[![CI](https://github.com/bapuji-dirisala/ecommerce-aws-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/bapuji-dirisala/ecommerce-aws-platform/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> AWS-native e-commerce lakehouse — three ingestion paths into S3, Glue +
> Lambda jobs orchestrated by Step Functions, Lake Formation governance,
> Redshift Serverless + Spectrum for BI, SNS/SQS fan-out for downstream
> consumers. Every service in Terraform; every IAM policy hand-written;
> every line runs locally against LocalStack + DuckDB for a $0 demo.

**Status (2026-10-25):** Phase 1 shipped — Terraform baseline (three S3 medallion buckets with versioning + SSE + public-access-block + glacier lifecycle; three least-privilege IAM service roles for Lambda/Glue/Firehose) runnable against both LocalStack and real AWS.

## Why this project

Senior AWS data engineer interviews probe three things: **the breadth
of the AWS data stack** you've touched, **the depth** of your IaC and
IAM discipline, and **the governance story** (Lake Formation, Athena
workgroups, least-privilege roles). This repo answers all three with
reviewable code — thirteen AWS services wired end-to-end in Terraform,
every IAM policy written by hand, LocalStack and DuckDB as the free
local stand-ins so a reader can clone and run everything without an
AWS account or any paid service.

## Cost model

**$0 locally, $0 in CI, $10-30/mo if a reader chooses to deploy.**

| Service | Local demo (free) | Production path (code ships; reader deploys optionally) |
|---------|-------------------|--------------------------------------------------------|
| S3 + Lambda + SNS/SQS + API Gateway + Firehose + EventBridge | LocalStack Community (`localstack start -d`) | Terraform `apply` to real AWS |
| Athena + Redshift Serverless + Spectrum | DuckDB over Parquet-on-disk | Terraform + SQL DDL + external tables |
| Glue (ETL + Data Catalog) | PySpark + delta-rs locally | Terraform + committed Glue job scripts |
| Step Functions | Python state-machine driver | Terraform + committed ASL JSON |
| Lake Formation | n/a (no local emulator) | Terraform + LF-tag + row-filter policies |
| IAM | n/a (no local policies needed) | Hand-written JSON policies, committed |
| CI | GHA on a public repo = unlimited free minutes | — |

Terraform artifacts are the deliverable, not the deployment.
Hiring managers read reviewable IaC + handler code; they don't need
me to spend money proving it works.

## Tech stack

| Layer | Tech |
|-------|------|
| Language | Python 3.11 · SQL · HCL (Terraform) |
| Object store | AWS S3 (LocalStack locally) |
| Compute | AWS Glue · AWS Lambda · Kinesis Firehose |
| Orchestration | AWS Step Functions · EventBridge |
| Edge | API Gateway + Lambda · SNS + SQS fan-out |
| Query | Athena (DuckDB locally) |
| Warehouse | Redshift Serverless + Spectrum (DuckDB locally) |
| Governance | Lake Formation · hand-written IAM policies |
| IaC | Terraform (remote state on S3 + DynamoDB lock) |
| Dev tooling | ruff · mypy · pre-commit · pytest · moto · LocalStack |
| CI | GitHub Actions (unlimited free on public repos) |

## Twelve-phase roadmap

| #  | Phase                                          | Doc                                                           | Status      |
|----|------------------------------------------------|---------------------------------------------------------------|-------------|
| 0  | Scaffolding, tooling, CI                       | [docs/phase-00-scaffolding.md](docs/phase-00-scaffolding.md)  | shipped     |
| 1  | Terraform baseline — S3 buckets + IAM roles (LocalStack-ready)| [docs/phase-01-terraform-baseline.md](docs/phase-01-terraform-baseline.md) | shipped     |
| 2  | Synthetic generator — orders / products / customers / clickstream | *coming soon*                              | planned     |
| 3  | Ingest path 1 — API Gateway → Lambda → S3 bronze (real-time orders) | *coming soon*                            | planned     |
| 4  | Ingest path 2 — Partner CSV → S3 drop → EventBridge → Lambda → bronze | *coming soon*                          | planned     |
| 5  | Ingest path 3 — Kinesis Firehose → S3 bronze (clickstream, hourly) | *coming soon*                             | planned     |
| 6  | Glue Data Catalog + crawlers; Glue job: bronze → silver cast/dedup | *coming soon*                             | planned     |
| 7  | Silver → gold Spark job (local PySpark; Glue production target) | *coming soon*                                | planned     |
| 8  | Step Functions orchestration — DAG tying bronze → silver → gold | *coming soon*                                | planned     |
| 9  | Lake Formation — row-level security, column masking, LF-tag grants | *coming soon*                             | planned     |
| 10 | Redshift Serverless + Spectrum — external tables over S3 gold | *coming soon*                                 | planned     |
| 11 | SNS/SQS fan-out — order-status notifications + Lambda consumer | *coming soon*                                | planned     |
| 12 | Observability + CI/CD — CloudWatch dashboards, GHA terraform plan/apply | *coming soon*                        | planned     |

Each phase ships as one small, focused commit. See
[`docs/`](docs/) for per-phase design + rationale.

## Getting started (free local path)

Prerequisites:

- macOS or Linux, Python 3.11
- [Colima](https://github.com/abiosoft/colima) (`brew install colima && colima start --cpu 4 --memory 8`)
- Terraform ≥ 1.6 (`brew install terraform`)
- LocalStack Community (`pip install localstack`)
- AWS CLI (`brew install awscli`) + awscli-local (`pip install awscli-local`)

```bash
git clone https://github.com/bapuji-dirisala/ecommerce-aws-platform.git
cd ecommerce-aws-platform

python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install

# Verify base install:
pytest -q
ecom-aws --version
```

Install extras as you work through each phase:

```bash
pip install -e ".[generator]"          # Phase 2
pip install -e ".[aws]"                # Phase 3+ (boto3 + moto + LocalStack client)
pip install -e ".[local-warehouse]"    # Phase 6+ (PySpark + delta-rs + DuckDB)
pip install -e ".[api]"                # Phase 11 (FastAPI)
```

## Project conventions

- **Code style.** Minimal inline comments; code is self-explanatory via
  naming + short docstrings. `from __future__ import annotations` at
  the top of every module. Type hints on all public functions. Long
  design rationale lives in `docs/phase-NN-*.md`, not in code comments.
- **Commit style.** Conventional-commit prefixes (`chore:`, `feat:`,
  `fix:`, `docs:`, `test:`, `refactor:`, `perf:`, `build:`, `ci:`).
  Subject ≤ 72 chars, imperative mood. One phase per commit when
  possible. Push with `--force-with-lease`.
- **Pre-commit.** ruff + mypy + hygiene set runs on every commit.
  `pre-commit run --all-files` before pushing to catch anything the
  hook missed.

## License

MIT — see [LICENSE](LICENSE).
