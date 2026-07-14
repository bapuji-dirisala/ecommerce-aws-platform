#!/usr/bin/env bash
#
# Package the orders-api Lambda for deployment.
# Output: build/lambda-orders-api.zip
#
# The zip contains:
#   - handler.py (the Lambda entrypoint)
#   - the ecom_aws package (installed via pip --target)
#   - its runtime deps (boto3 is in the Lambda runtime so we skip it)
#
# Usage:
#   scripts/build-lambda.sh orders-api

set -euo pipefail

cd "$(dirname "$0")/.."

name="${1:-orders-api}"
src_dir="lambdas/${name//-/_}"
out_dir="build/lambda-${name}"
zip_file="build/lambda-${name}.zip"

if [[ ! -d "$src_dir" ]]; then
  echo "no Lambda source at $src_dir" >&2
  exit 2
fi

rm -rf "$out_dir" "$zip_file"
mkdir -p "$out_dir"

# Copy the handler.
cp "$src_dir"/*.py "$out_dir/"

# Install the package into the bundle. --no-deps because boto3 ships in
# the Lambda runtime image.
pip install --target "$out_dir" --no-deps --upgrade . >/dev/null

(
  cd "$out_dir"
  zip -r -q "../../$zip_file" .
)

size_kb=$(du -k "$zip_file" | awk '{print $1}')
echo "built $zip_file (${size_kb} KB)"
