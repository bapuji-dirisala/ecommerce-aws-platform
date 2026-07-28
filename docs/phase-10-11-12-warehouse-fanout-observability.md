# Phases 10 + 11 + 12 — Redshift Serverless + Spectrum, SNS/SQS fan-out, Observability

The last three phases bolt the finished medallion onto a serving layer,
a reactive event spine, and a CloudWatch dashboard — all with
hand-written IAM and gated behind variables so `terraform validate`
passes without a real deploy.

## Phase 10 — Redshift Serverless + Spectrum

```
      ┌───────────────────────────┐
      │ Redshift Serverless       │
      │ namespace: ecom-rs-...    │
      │ workgroup: 8–32 RPU       │
      └──────────────┬────────────┘
                     │  Spectrum (IAM role)
                     ▼
      ┌───────────────────────────┐
      │ Glue Data Catalog         │
      │   ecom_gold               │
      │     fact_daily_orders     │
      └──────────────┬────────────┘
                     │
                     ▼
      ┌───────────────────────────┐
      │ S3 gold bucket            │
      │ orders/event_date=.../    │
      └───────────────────────────┘
```

The analyst-facing surface is `gold_marts.v_daily_orders_us` and
`gold_marts.v_monthly_gmv_by_country`, both views over
`spectrum_gold.fact_daily_orders` — a Spectrum external table that
points at the Phase 7 silver→gold job output. No Redshift tables; the
warehouse scales to zero when nobody is querying.

Files:

- `redshift/01_schema.sql` — creates `gold_marts` + the Spectrum
  external schema. The IAM role ARN is templated so the same SQL runs
  across environments.
- `redshift/02_views.sql` — business views (US daily, monthly GMV by
  country). `CREATE OR REPLACE VIEW` so redeploys are idempotent.
- `terraform/modules/redshift-serverless/` — namespace + workgroup +
  Spectrum role (`glue:GetTable` + `s3:GetObject` on the gold bucket only).

Why Serverless, not provisioned: the portfolio demo never has sustained
load, so paying only for query time + a minimum 8-RPU floor is strictly
cheaper than keeping a dc2.large hot. Spectrum keeps the warehouse size
unrelated to the lakehouse size.

## Phase 11 — SNS → 2× SQS fan-out for order-status events

```
         publisher
            │
            ▼
     SNS: order-status
         ┌──┴──┐
         ▼     ▼
  SQS: analytics   SQS: notifications
         │              │
         ▼              ▼
   Lambda consumer   (future: email/push)
         │              │
         ▼              ▼
     CloudWatch     dead-letter queue
```

Design decisions worth defending:

- **Fan-out via SQS, not direct Lambda targets.** The analytics path and
  the notifications path have very different durability/retention
  requirements, so each gets its own queue with its own
  `visibility_timeout_seconds`, `message_retention_seconds`, and DLQ.
  A single Lambda subscription couldn't do that.
- **Max-receive = 5 on every queue.** Poison messages get moved to the
  DLQ after five visibility expirations; the alarm in Phase 12 wakes up
  when the DLQ is non-empty.
- **SNS→SQS wrapper preserved** (`raw_message_delivery = false`) so the
  publisher metadata is visible to the consumer; the consumer unwraps
  `body.Message` as JSON.
- **KMS encryption on everything** — SNS + both SQS queues + both DLQs
  all use AWS-managed CMKs (`alias/aws/sns`, `alias/aws/sqs`).
- **The consumer Lambda is gated on its zip var.** `terraform validate`
  stays green without a build; a real deploy wires it in by setting
  `TF_VAR_lambda_order_status_consumer_zip=/path/to/handler.zip`.

Files:

- `src/ecom_aws/notify/order_status_consumer.py` — the shared handler.
  Parses the SNS envelope, emits a CloudWatch metric per transition.
- `lambdas/order_status_consumer/handler.py` — Lambda zip entrypoint.
- `terraform/modules/sns-sqs-fanout/` — SNS + 2 queues + 2 DLQs +
  queue policies + optional Lambda consumer.

## Phase 12 — Observability (CloudWatch dashboard + alarms)

The dashboard surfaces three signals in one view:

- **Bronze ingest objects (24h)** — one series per dataset (orders,
  partner_products, clickstream). Emitted by the `ingest_summary`
  Lambda invoked from the Step Functions `ParallelIngestSummary` state.
- **Order-status transitions** — stacked time series by `NewStatus`
  (created, paid, shipped, cancelled). Emitted by the Phase 11 consumer.
- **Glue job runs** — completed vs failed tasks on the orders b2s job.

Alarms:

- **`sfn-failures`** — one or more Step Functions executions failed in
  a 5-minute window. Alarms + OKs both fire to the SNS topic from
  Phase 11, so ops wake up on failure and get the all-clear on
  recovery.
- **`analytics-dlq-depth`** — the order-status analytics DLQ has at
  least one message visible.

Files:

- `lambdas/ingest_summary/handler.py` — counts bronze objects per
  dataset × event_date and emits two CloudWatch metrics.
- `terraform/modules/observability/` — dashboard + alarms. The dashboard
  is always on; alarms are gated on the ARNs being present.

## Running against real AWS

```bash
# Phase 10
export TF_VAR_enable_redshift_serverless=true
export TF_VAR_redshift_admin_password='…'

# Phase 11
cd lambdas/order_status_consumer && zip -r /tmp/order-status.zip .
export TF_VAR_lambda_order_status_consumer_zip=/tmp/order-status.zip

# Phase 12 always on

cd terraform && terraform init && terraform plan
```

After deploy, apply the Redshift SQL from a Query Editor v2 session or
via `aws redshift-data execute-statement`:

```bash
sed "s|\${REDSHIFT_IAM_ROLE_ARN}|$(terraform output -raw spectrum_role_arn)|" redshift/01_schema.sql
```
