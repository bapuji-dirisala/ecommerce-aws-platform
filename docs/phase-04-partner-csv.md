# Phase 4 — Partner CSV → EventBridge → Lambda → S3 bronze

**Status:** Shipped. Second of three ingestion paths. Partners drop CSV
export files into a dedicated drop bucket; S3 EventBridge integration
fires an `Object Created` event; EventBridge routes to a Lambda that
parses, normalizes, and lands JSONL in the exact same bronze layout
Phase 3's API handler produces.

## Flow

```
Partner        S3 drop bucket             EventBridge default bus
   │  PUT         │                              │
   ├──────────────▶ drop/orders-2026-02-14.csv   │
   │              ├─ Object Created ─────────────▶ rule: prefix drop/
   │              │                              │       │
   │              │                              │       ▼
   │              │                              │   Lambda (python3.11)
   │              │                              │   ecom_aws.ingest.partner_csv
   │              │                              │       │
   │              │                              │       │  s3.get_object (drop)
   │              │                              │       │  s3.put_object (bronze)
   │              │                              │       ▼
   │              │                              │   S3 bronze
   │              │                              │   orders/event_date=YYYY-MM-DD/
   │              │                              │     partner-csv-20260214T120000-…
```

## Design choices worth defending

1. **Separate drop bucket from bronze bucket.** Partners get
   `s3:PutObject` on `drop/*` of the drop bucket only. The Lambda has
   its own IAM role that reads drop + writes bronze. Nothing partner-
   facing can touch bronze directly. This is the standard "DMZ bucket"
   pattern senior architects expect.
2. **Native S3 EventBridge integration, not S3 notifications.** The
   EventBridge path is the current best-practice route: better filter
   expressions, retry policies, DLQ wiring, cross-account targets.
   Enabled via `aws_s3_bucket_notification { eventbridge = true }`.
3. **Prefix-filtered rule.** Only objects under `drop/` fire the Lambda.
   Everything else (manifests, backfill files, admin uploads) stays
   silent. The EventBridge rule's `event_pattern` locks it down.
4. **Non-destructive processing.** Original CSV stays in the drop
   bucket (compliance audit trail). Lambda failures don't delete the
   source. A dedicated lifecycle rule on the drop bucket can archive
   after N days — kept out of this module intentionally so operators
   decide the retention policy.
5. **Shared bronze envelope.** `partner_csv.py` imports the same
   `record_envelope()` + `bronze_key()` helpers as `orders_api.py`.
   Silver sees one unified namespace: `orders/event_date=.../…` with
   `ingest_source` as the only path-specific tag.
6. **Rejects, don't crash.** Malformed CSVs return `{"status":
   "rejected", "error": …}` from the handler rather than throwing. One
   bad file doesn't stop EventBridge from processing the next one.
   Logs + CloudWatch metrics catch the rejection count; alerts live in
   Phase 12.
7. **UTF-8 BOM tolerance.** Enough partners export via Excel that
   handling the BOM up front saves a weekend of "why is the first
   column named `\ufeffcustomer_id`" tickets.

## File layout

| File | Purpose |
|------|---------|
| `src/ecom_aws/ingest/partner_csv.py` | The Lambda handler — EventBridge event → CSV parse → bronze JSONL. |
| `lambdas/partner_csv/handler.py` | Deployment entrypoint — thin re-export. |
| `terraform/modules/partner-csv-ingest/` | Drop bucket + encryption/versioning/block-public + S3→EventBridge integration + Lambda + rule + target + log group + invoke permission. |
| `tests/test_ingest_partner_csv.py` | moto-driven tests covering happy path, header-only, missing column, BOM handling, metadata capture, event parsing failure. |

## Running it

### Unit tests

```bash
pip install -e ".[dev,generator,aws]"
pytest tests/test_ingest_partner_csv.py -v
```

### LocalStack demo

```bash
localstack start -d
awslocal s3 mb s3://ecom-local-bronze-local
awslocal s3 mb s3://ecom-local-partner-drop-local

# Drop a CSV in the right prefix:
cat > /tmp/partner-orders.csv <<EOF
order_id,customer_id,placed_at,total_usd,ship_country
ORD001,CUS001,2026-02-14T10:00:00Z,49.99,US
ORD002,CUS002,2026-02-14T10:05:00Z,129.00,US
EOF
awslocal s3 cp /tmp/partner-orders.csv s3://ecom-local-partner-drop-local/drop/

# EventBridge → Lambda happens automatically. Confirm bronze got the data:
awslocal s3 ls s3://ecom-local-bronze-local/orders/ --recursive
```

### Terraform validate

```bash
./scripts/tf-local.sh validate
```

Deploy would set `lambda_partner_csv_zip = ../build/lambda-partner-csv.zip`
after `scripts/build-lambda.sh partner-csv`.

## What's next

Phase 5 adds the third ingestion path — Kinesis Firehose buffering
clickstream events into hourly bronze files. Firehose's native S3
destination requires no handler code; the Terraform module shows the
proper delivery-role scoping + Parquet conversion via a Glue schema.
