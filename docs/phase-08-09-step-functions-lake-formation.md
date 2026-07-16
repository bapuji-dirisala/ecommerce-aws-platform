# Phase 8 + 9 — Step Functions orchestration + Lake Formation governance

**Status:** Shipped. One Step Functions STANDARD state machine orchestrates
the full orders medallion DAG; Lake Formation registers the three S3
medallion locations, defines three LF-tags, assigns tags to each
database, and grants tag-based SELECT to an analyst role.

## Step Functions DAG

```
                 ┌──────────────────────────────┐
                 │  ParallelIngestSummary       │
                 │  ┌────────┐┌────────┐┌─────┐ │
                 │  │API Lmbda││Partner││Firehose│
                 │  │Summary ││Summary ││Summary│
                 │  └────────┘└────────┘└───────┘│
                 └──────────────┬───────────────┘
                                ▼
                 ┌──────────────────────────────┐
                 │   RunBronzeToSilver          │
                 │   Glue job (startJobRun.sync)│
                 └──────────────┬───────────────┘
                                ▼                 ┌───────────────┐
                 ┌──────────────────────────────┐ │ NotifyFailure │
                 │   RunSilverToGold            │─▶│ SNS publish   │
                 │   Glue job (startJobRun.sync)│ └───────┬───────┘
                 └──────────────┬───────────────┘         ▼
                                ▼                  ┌───────┐
                      ┌─────────────────┐          │ Fail  │
                      │ NotifySuccess   │          └───────┘
                      │ SNS publish     │
                      └─────────────────┘
```

- Parallel branches summarize what landed in bronze per source
- Both Glue invocations use `startJobRun.sync` so the DAG waits for completion
- Both have `Retry` (3 attempts for TaskFailed, 5 for ConcurrentRunsExceededException)
- Both have `Catch` → `NotifyFailure` → `Fail`
- Success + failure both publish to SNS (consumer in Phase 11)

### Reviewable artifacts

```
stepfunctions/orders_medallion_dag.asl.json         # The whole DAG as ASL JSON
src/ecom_aws/orchestrate/local_runner.py            # Local Python executor
terraform/modules/step-functions/                   # SFN + exec role + log group
```

## Lake Formation baseline

Three LF-tags with controlled value lists:

| Tag                    | Values                                   |
| ---------------------- | ---------------------------------------- |
| `data_classification`  | public, internal, confidential, restricted |
| `sensitivity`          | low, medium, high, pii                   |
| `data_zone`            | bronze, silver, gold                     |

Database-level assignments:

| Database       | `data_zone` | `sensitivity` |
| -------------- | ----------- | ------------- |
| `ecom_bronze`  | bronze      | medium        |
| `ecom_silver`  | silver      | low           |
| `ecom_gold`    | gold        | low           |

An analyst IAM role gets tag-based SELECT:

```
Grant SELECT + DESCRIBE
WHERE sensitivity ∈ {low} AND data_zone ∈ {silver, gold}
```

So one grant covers "any silver or gold table that isn't PII" without
listing them.

### Reviewable artifacts

```
lake-formation/lf-tags.json                        # LF-tag definitions as JSON
lake-formation/data-filters.sql                    # Data-cell filter example (SQL)
terraform/modules/lake-formation/                  # LF registration + tags + grants
```

## Design decisions worth defending

1. **ASL JSON lives in the repo, not the UI.** Every DAG change is a
   pull request. Terraform `file()` loads it; `terraform plan` diffs
   show exactly what changed.
2. **`startJobRun.sync` not fire-and-forget.** The DAG must wait for
   Glue job completion to make retry + catch meaningful. Async would
   lose failure visibility.
3. **Retry + Catch on every Glue task.** Glue's `ConcurrentRunsExceededException`
   is the #1 real-world failure; the retry policy for it is distinct
   (5 attempts, long backoff) from the generic `TaskFailed` policy
   (2 attempts).
4. **CloudWatch logging on, level=ERROR.** Full execution data captured
   on failure (incl. input + output), not all the time (cost).
5. **Hand-written SFN execution role.** No AWS-managed catch-all.
   Role gets Glue StartJobRun on the two Glue jobs by ARN, Lambda
   Invoke on the summary Lambda by ARN, SNS Publish on the notify
   topic. Logs is wildcard per AWS documentation (SFN requirement).
6. **LF-tags not resource grants.** Tag-based grants scale to new
   tables automatically; resource grants would require updating the
   grant list every time silver gets a new table.
7. **`sensitivity` and `data_zone` as separate tags.** Composable
   expressions: an actuary might get `sensitivity ∈ {low,medium} AND
   data_zone = gold`; an engineer `sensitivity = * AND data_zone =
   silver`. Separable tags make this easy.

## Running it

### Unit tests

```bash
pip install -e ".[dev,generator,aws,local-warehouse]"
pytest tests/test_orchestrate.py -v
```

### Local DAG demo

```bash
# generate + ingest first
ecom-aws generate all --out data/bronze/local
ecom-aws ingest-local orders-api --count 100

# run the DAG locally
python -c "
from pathlib import Path
from ecom_aws.orchestrate import run_orders_dag_locally
r = run_orders_dag_locally(
    bronze_jsonl=Path('data/bronze/local/orders.jsonl'),
    silver_root=Path('data/silver'),
    gold_root=Path('data/gold'),
)
print(r.status, r.steps)
"
```

### Terraform validate

```bash
./scripts/tf-local.sh validate
```

## What's next

Phase 10 adds Redshift Serverless + Spectrum — one workgroup/namespace +
external tables over the S3 gold prefix, so analysts can `SELECT * FROM
spectrum.fact_daily_orders` without copying data. Phase 11 adds the SNS
+ SQS fan-out that the state machine already publishes to.
