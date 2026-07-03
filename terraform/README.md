# terraform/

Phase 1 baseline. Three S3 buckets (bronze/silver/gold) with versioning
+ lifecycle + SSE + public-access-block, plus three least-privilege IAM
service roles (Lambda / Glue / Firehose). Later phases attach workload
modules (api-ingest, firehose-ingest, glue-jobs, step-functions,
lake-formation, redshift, sns-sqs) on top of this baseline.

## Layout

```
terraform/
├── versions.tf              # TF 1.6+, AWS provider 5.70+
├── providers.tf             # dual-mode: real AWS or LocalStack
├── variables.tf             # project / environment / region / use_localstack
├── main.tf                  # root composition — wires both modules
├── outputs.tf               # bucket names, role ARNs
├── backend.tf.example       # remote-state template; copy to backend.tf
│
├── environments/
│   ├── local/terraform.tfvars           # LocalStack defaults
│   └── dev/terraform.tfvars.example     # real-AWS reference
│
└── modules/
    ├── s3-lakehouse/        # 3 buckets, DRY via for_each over layer names
    └── iam-baseline/        # 3 service roles, each with inline policy
```

## Running locally (free, LocalStack)

```bash
# One-time: start LocalStack
colima start --cpu 4 --memory 8      # if Docker Desktop is unavailable
localstack start -d                   # LocalStack Community (free)

# Terraform
cd terraform/
terraform init -backend=false         # no remote state locally
terraform fmt -check                  # formatting gate
terraform validate                    # offline validation
terraform plan -var-file=environments/local/terraform.tfvars
terraform apply -var-file=environments/local/terraform.tfvars

# Verify (via awscli-local, which prefixes awslocal to every awscli call)
awslocal s3 ls
```

## Running on real AWS (optional, costs real money)

```bash
# Bootstrap remote state (one-time per account)
aws s3api create-bucket --bucket my-ecom-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket my-ecom-tfstate \
    --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name my-ecom-tfstate-lock \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST

# Enable remote backend
cp backend.tf.example backend.tf      # then edit the bucket + table names

# Deploy
cp environments/dev/terraform.tfvars.example environments/dev/terraform.tfvars
terraform init                        # picks up the remote backend
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

## CI contract

A `terraform-check` GHA job runs on every push + PR:

1. `terraform fmt -recursive -check` — formatting
2. `terraform init -backend=false` — offline init
3. `terraform validate` — HCL + provider schema check

Deployment never happens from CI — the Terraform here is the portfolio
deliverable, not a production pipeline.
