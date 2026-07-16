# Phase 5 — Clickstream via Kinesis Data Firehose → S3 bronze

**Status:** Shipped. Third of three ingestion paths. Producers push
clickstream events to a Firehose delivery stream; Firehose buffers +
compresses + batches + writes to the bronze bucket in GZIP'd NDJSON
hourly partitions. No code runs on the ingest edge — Firehose owns it.

## Flow

```
Producer app              Kinesis Data Firehose           S3 bronze
   │ PutRecordBatch (100-record batches)
   ├──────────────────────▶ delivery stream buffer
   │                         (5 MiB OR 60s)
   │                        │
   │                        │ GZIP compress
   │                        │ hive-partition prefix
   │                        │
   │                        ▼
   │                       s3://.../bronze/clickstream/
   │                         event_date=YYYY-MM-DD/
   │                           hour=HH/
   │                             firehose-TS-UUID.gz
```

## Design choices

1. **Firehose, not Kinesis Data Streams.** Our pattern is "produce
   events, deliver to S3". KDS would add a per-shard-hour cost + a
   custom consumer we don't need. Firehose is $0.029/GB with no idle
   cost — the right answer for clickstream.
2. **GZIP compression**. 60-80% size reduction on JSON. Athena +
   Redshift Spectrum read GZIP transparently.
3. **5 MiB / 60s buffering**. Produces one object per minute at light
   demo load, one object every 5-15s under production load. Keeps S3
   object count reasonable while still being near-real-time.
4. **Hive-partitioned prefix** via Firehose timestamp functions
   (`!{timestamp:yyyy-MM-dd}` / `!{timestamp:HH}`). Athena partition
   projection reads this layout with zero crawler calls.
5. **Dedicated `firehose-delivery` IAM role from Phase 1**.
   `BronzeAppend` policy already there — Firehose only needs
   `s3:AbortMultipartUpload`, `s3:GetBucketLocation`,
   `s3:GetObject`, `s3:ListBucket`, `s3:ListBucketMultipartUploads`,
   `s3:PutObject` on the bronze bucket. Hand-written, scoped by ARN.
6. **CloudWatch logging on**. Delivery failures land in the
   `S3Delivery` log stream + the `error_output_prefix` in S3.
7. **Trailing newline per record**. Firehose doesn't add framing — our
   producer appends `\n` so S3 objects are valid NDJSON when unpacked.

## File layout

| File | Purpose |
|------|---------|
| `src/ecom_aws/ingest/firehose_client.py` | Minimal client wrapper — serialize, batch, PutRecordBatch, count failures. |
| `src/ecom_aws/ingest/local_driver.py` | `drive_clickstream_firehose_local()` — generator → Firehose demo loop. |
| `terraform/modules/clickstream-firehose/` | Delivery stream + CloudWatch log group + log stream + extended S3 destination config. |
| `tests/test_ingest_firehose.py` | moto-driven Firehose tests: single batch, large batch (3× chunks), datetime serialization, stream override. |

## Running it

### Unit tests

```bash
pip install -e ".[dev,generator,aws]"
pytest tests/test_ingest_firehose.py -v
```

### LocalStack demo

```bash
localstack start -d
awslocal s3 mb s3://ecom-local-bronze-local

# Terraform apply (or hand-create the stream for a quick demo).
./scripts/tf-local.sh plan

# Push 500 events through Firehose:
ecom-aws ingest-local clickstream-firehose --count 500 --seed 42

# After 60s (buffering interval), inspect the delivered objects:
awslocal s3 ls s3://ecom-local-bronze-local/clickstream/ --recursive
```

### Terraform validate

```bash
./scripts/tf-local.sh validate
```

The Firehose module is **always on** (not gated on a Lambda zip) — the
stream has no deployment artifact, only configuration.

## What's next

Phase 6 brings Glue into the picture: Data Catalog + crawlers register
the bronze zone as schema-on-read tables, then a bronze → silver Glue
PySpark job casts raw NDJSON to typed Parquet, dedupes by business key,
and writes to the silver bucket. Local path uses PySpark + delta-rs so
the job runs on a laptop before anyone pays for Glue DPU hours.
