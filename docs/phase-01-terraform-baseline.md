# Phase 1 — Terraform baseline

**Status:** shipped (2026-10-25)

## Goal

Lay down the three S3 lakehouse buckets and three IAM service roles
that every subsequent phase depends on, with the same Terraform tree
runnable against LocalStack (free, local) or real AWS (paid, optional)
via a single `use_localstack` variable flip.

## What this phase delivers

- **`terraform/versions.tf`** — Terraform ≥ 1.6, AWS provider 5.70+,
  random 3.x. Version pins keep CI builds reproducible.
- **`terraform/providers.tf`** — one AWS provider block with
  conditional `endpoints {}` for LocalStack. The committed modules
  don't know or care which backend is active.
- **`terraform/variables.tf`** — `project`, `environment` (validated
  against local/dev/staging/prod), `aws_region`, `use_localstack`,
  `bucket_name_suffix`, `lakehouse_retention_days`.
- **`terraform/main.tf`** — wires `s3-lakehouse` + `iam-baseline`
  modules; random suffix generation so bucket names are globally
  unique on first apply.
- **`terraform/modules/s3-lakehouse/`** — three buckets
  (`${prefix}-bronze-${suffix}`, `-silver-`, `-gold-`) built via
  `for_each` on a layer map. Each gets versioning + SSE-S3 + full
  public-access-block + lifecycle (glacier transition on non-current
  versions, abort incomplete multipart uploads after 7 days).
- **`terraform/modules/iam-baseline/`** — three service roles
  (`lambda-exec`, `glue-service`, `firehose-delivery`), each with a
  hand-written inline policy scoped to the lakehouse buckets. No
  AWS-managed catch-all policies. Trust policies pin
  `sts:AssumeRole` to the specific AWS service that will use the role.
- **`terraform/environments/local/terraform.tfvars`** —
  LocalStack-flavored defaults (7-day retention).
- **`terraform/environments/dev/terraform.tfvars.example`** — real-AWS
  reference (90-day retention) for a reader deploying to their own
  account.
- **`terraform/backend.tf.example`** — remote-state template (S3 +
  DynamoDB lock); real `backend.tf` is gitignored.
- **`scripts/tf-local.sh`** — convenience wrapper so a reader doesn't
  have to remember the `-var-file` flag.
- **`terraform/README.md`** — layout, run instructions for both local
  + real-AWS paths, CI contract.
- **`.github/workflows/ci.yml`** — new `terraform-check` job (fmt +
  init + validate on every push + PR; uses `hashicorp/setup-terraform@v3`).

## Design decisions

### Single tree, two backends via `use_localstack`

The naive alternative is two providers (one for real AWS, one for
LocalStack) and a `providers_localstack.tf` override pattern. That
means two copies of every endpoint config, drift between the two over
time, and a reader having to understand two near-identical files.

Instead: one provider block, a `dynamic "endpoints"` block gated on
`use_localstack`, and a `.tfvars` file per environment that picks the
mode. The committed modules are backend-agnostic — same `for_each`,
same policy JSON, same resource names — so there's zero duplication
between "local demo" and "production path".

### DRY buckets via `for_each` over layer names

Three near-identical buckets could easily grow to twelve near-identical
resource blocks. Instead: a `locals.layers` map of `{ bronze → "...",
silver → "...", gold → "..." }` and every bucket + versioning +
encryption + public-access-block + lifecycle is a single `for_each`
resource. Adding a `platinum` layer in Phase 7+ is a one-line map
addition.

### Hand-written IAM, pinned trust, scoped resources

Senior AWS DE interviews probe IAM depth. Every policy here is
hand-written (no `arn:aws:iam::aws:policy/service-role/...`), every
trust policy pins the exact `Service` principal (`lambda.amazonaws.com`,
`glue.amazonaws.com`, `firehose.amazonaws.com`), every resource list
is scoped to specific bucket ARNs (no `arn:aws:s3:::*`). The three
roles have different and overlapping read/write patterns across the
medallion layers — Lambda writes bronze+silver, Glue reads bronze+silver
+ writes silver+gold, Firehose appends to bronze only.

### Public access blocked at the account posture, not just the bucket

Every bucket gets a full `aws_s3_bucket_public_access_block` with all
four controls (`block_public_acls`, `block_public_policy`,
`ignore_public_acls`, `restrict_public_buckets`) set to `true`. This
is 2026 S3 security table stakes — the account-level public-access-block
is a separate control, but defense-in-depth at the bucket level
guarantees a reader who clones + applies against a non-locked-down
account still gets secure buckets.

### Non-current version lifecycle, not aggressive deletion

Versioning is on; lifecycle moves *non-current* versions to Glacier
after `var.noncurrent_version_days` (7 days local, 90 days prod)
rather than deleting them. Current versions never expire. This gives
point-in-time recovery for the lakehouse while keeping cold-storage
costs minimal.

## How to run

```bash
# Prereqs (free)
brew install terraform                # or asdf plugin add terraform
colima start --cpu 4 --memory 8       # Docker runtime
pip install localstack awscli-local
localstack start -d

# Validate (offline, no cost)
cd terraform
terraform init -backend=false
terraform fmt -check
terraform validate

# Apply locally
terraform plan -var-file=environments/local/terraform.tfvars
terraform apply -var-file=environments/local/terraform.tfvars

# Verify
awslocal s3 ls                        # three buckets listed
awslocal iam list-roles --query 'Roles[?starts_with(RoleName, `ecom-local`)].RoleName'
```

Convenience wrapper:

```bash
./scripts/tf-local.sh plan
./scripts/tf-local.sh apply -auto-approve
./scripts/tf-local.sh destroy -auto-approve
```

## Gotchas

- **S3 bucket name uniqueness is global on real AWS**, local on
  LocalStack. The random suffix handles the real-AWS case; LocalStack
  users can pin a short, memorable suffix via
  `bucket_name_suffix = "local"` as in the committed local tfvars.

- **LocalStack Community doesn't fully implement every lifecycle
  edge case.** Non-current version transitions log but don't actually
  move objects to a Glacier equivalent — the config is there as
  reviewable code; the real transitions happen only on real AWS.

- **`terraform validate` requires provider schemas**, which requires
  `terraform init`. CI runs `init -backend=false` so it skips
  configuring remote state but still downloads the AWS provider.

- **Lifecycle rule needs an explicit `filter {}`** block (even if
  empty) for provider 5.x. Omitting it fails with a deprecated-syntax
  warning. The committed modules include it.

## References

- [`../terraform/README.md`](../terraform/README.md) — layout + run instructions.
- [`../README.md`](../README.md) — 12-phase roadmap.

## Next phase

**Phase 2** — synthetic generator. Deterministic Faker-driven orders /
products / customers / clickstream Parquet, same pattern as the P3
banking generator. Phase 3 ingestion paths will land this generated
data into the Phase 1 bronze bucket.
