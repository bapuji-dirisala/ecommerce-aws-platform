#!/usr/bin/env bash
# Convenience wrapper for running terraform against the LocalStack-flavored
# tfvars without having to remember the -var-file flag every invocation.
#
# Usage: ./scripts/tf-local.sh plan
#        ./scripts/tf-local.sh apply -auto-approve
#        ./scripts/tf-local.sh destroy -auto-approve
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TF_DIR="${SCRIPT_DIR}/../terraform"
TFVARS="${TF_DIR}/environments/local/terraform.tfvars"

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <terraform-command> [args...]" >&2
  echo "example: $0 plan" >&2
  exit 2
fi

CMD="$1"
shift

# Lazy init so first-time users don't need to remember a separate step.
if [[ ! -d "${TF_DIR}/.terraform" ]]; then
  terraform -chdir="${TF_DIR}" init -backend=false
fi

case "${CMD}" in
  fmt|validate|init)
    exec terraform -chdir="${TF_DIR}" "${CMD}" "$@"
    ;;
  *)
    exec terraform -chdir="${TF_DIR}" "${CMD}" -var-file="${TFVARS}" "$@"
    ;;
esac
