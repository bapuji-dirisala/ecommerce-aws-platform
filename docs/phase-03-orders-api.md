# Phase 3 — Orders API Gateway → Lambda → S3 bronze

**Status:** Shipped. First of three ingestion paths. `POST /orders`
lands JSONL in `s3://…-bronze-…/orders/event_date=YYYY-MM-DD/…`
through a real Lambda — tested with `moto` locally, runnable against
LocalStack with no code changes.

## Flow

```
Caller                 API Gateway (HTTP API v2)
   │   POST /orders           │
   ├───────────────────────▶─ │
   │                          │                Lambda (python3.11)
   │                          ├─ AWS_PROXY ──▶ ecom_aws.ingest.orders_api
   │                          │                     │
   │                          │                     │  s3.put_object()
   │                          │                     ▼
   │                          │                S3 bronze bucket
   │                          │                 orders/event_date=YYYY-MM-DD/
   │                          │                   api-20260214T153000-abc123.jsonl
   │     201 + bronze_s3_uri  │                     │
   │ ◀──────────────────────  ◀─────────────────────┘
```

## What's reviewable

| File | Purpose |
|------|---------|
| `src/ecom_aws/ingest/orders_api.py` | The Lambda handler itself. Parses the API Gateway proxy event, validates minimum shape, wraps records in the standard bronze envelope, writes JSONL to S3. |
| `src/ecom_aws/ingest/bronze.py` | Shared helpers all three ingest paths use: `bronze_key()`, `record_envelope()`, `to_jsonl()`. Centralizes the Hive partition layout. |
| `src/ecom_aws/ingest/local_driver.py` | The "demo + Step Functions step" entry point — generates synthetic orders and invokes the handler against LocalStack. |
| `lambdas/orders_api/handler.py` | Deployment entrypoint — thin re-export so Terraform packaging is dumb-simple. |
| `terraform/modules/orders-api-ingest/` | Lambda + API Gateway HTTP API v2 + routes + integration + log groups + invoke permission. |
| `scripts/build-lambda.sh` | Packages the Lambda zip (pip --target + zip -r). |
| `tests/test_ingest_bronze.py` | Pins the shared helpers. |
| `tests/test_ingest_orders_api.py` | moto-driven handler tests: single + batch + partition date + 400 validation + object metadata. |

## Design decisions worth defending in an interview

1. **One S3 object per batch, one line per record.** Keeps S3 object
   count under control (bronze stays browsable) and keeps silver's
   parse logic trivial — standard JSONL, no custom framing.
2. **Shallow validation at the edge.** Bronze is "store first, prove
   later". The handler only rejects structural garbage (not JSON, no
   `order_id`). Business validation lives in silver.
3. **No DynamoDB "pending" / idempotency table.** The S3 write *is* the
   durability guarantee. Silver dedups by `(order_id, placed_at)`.
   Fewer moving parts, lower cost, clearer failure mode.
4. **HTTP API v2, not REST API v1.** v2 is ~70% cheaper, same proxy
   integration, same CloudWatch logging — unless you need request
   validators or usage plans (we don't), v2 is the right default.
5. **Env-var-only config.** `BRONZE_BUCKET` + optional
   `AWS_ENDPOINT_URL` is the entire configuration surface. Same code
   runs on LocalStack and on real AWS.
6. **Access logs on by default.** `access_log_settings` emits a JSON
   access log per request to CloudWatch — standard observability
   expectation at the edge.
7. **CloudWatch log retention set to 14 days** (not infinite). Prod
   log costs are a frequent interview topic; the module ships with a
   sane default.

## Running it

### Unit tests (moto, no network needed)

```bash
pip install -e ".[dev,generator,aws]"
pytest tests/test_ingest_orders_api.py tests/test_ingest_bronze.py -v
```

### LocalStack demo (optional)

```bash
# One-time setup.
pip install localstack awscli-local
localstack start -d

# Create the bronze bucket (what Terraform would do):
awslocal s3 mb s3://ecom-local-bronze-local

# Drive the handler against LocalStack.
ecom-aws ingest-local orders-api --count 20 --seed 42

# See the objects it wrote.
awslocal s3 ls s3://ecom-local-bronze-local/orders/ --recursive
```

### Terraform validate (no deploy)

```bash
./scripts/tf-local.sh validate
```

The orders-api Terraform module is gated behind `var.lambda_orders_api_zip`
— when empty (CI default), the module is skipped and the HCL still
`validate`s cleanly. A deploy would:

```bash
scripts/build-lambda.sh orders-api
cd terraform
terraform apply \
  -var-file=environments/dev/terraform.tfvars \
  -var='lambda_orders_api_zip=../build/lambda-orders-api.zip'
```

## What's next

Phase 4 adds the second ingest path — partner CSV files land in a drop
bucket, trigger an EventBridge rule, invoke a second Lambda that
normalizes and lands them in the same bronze layout. Both paths share
the `bronze.py` helpers so silver sees one unified namespace.
